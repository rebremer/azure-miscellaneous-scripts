-- Restore production table(s) to their state at a previous point in time, using the native
-- Delta time travel of the warehouse (zero-copy CLONE ... AT, retention 30 days).
--
--   EXEC ops.usp_restore_table @table_name = 'ALL',          @as_of_utc = '2026-11-17T13:37:25', @dry_run = 1; -- preview
--   EXEC ops.usp_restore_table @table_name = 'ALL',          @as_of_utc = '2026-11-17T13:37:25';               -- restore everything consistently
--   EXEC ops.usp_restore_table @table_name = 'fact_invoice', @as_of_utc = '2026-11-17T13:37:25';               -- restore one table
--
-- Pick @as_of_utc from ops.load_log: ops.load_log.started_utc of the BAD run = the state just before it.
-- All tables are swapped in ONE transaction; on any error nothing changes.
-- Limit: time travel cannot go back past an ALTER of the table (new column, row-level security policy, ...).
-- The procedure checks sys.tables.modify_date and refuses (error 50014, nothing changed) a restore point before the last ALTER.

-- A clone inherits row-level security predicates of its source (and a policy then blocks DROP TABLE),
-- so predicates are removed from the temporary ops.rst_* clones before they are read and dropped.
CREATE OR ALTER PROCEDURE ops.usp_clean_restore_clones
    @drop_tables bit = 1
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @sql nvarchar(max);

    SELECT @sql = STRING_AGG(CAST('ALTER SECURITY POLICY ' + QUOTENAME(ps.name) + '.' + QUOTENAME(pol.name)
                                  + ' DROP FILTER PREDICATE ON ops.' + QUOTENAME(t.name) + ';' AS nvarchar(max)), ' ')
    FROM sys.security_predicates AS sp
    JOIN sys.security_policies AS pol ON pol.object_id = sp.object_id
    JOIN sys.schemas AS ps ON ps.schema_id = pol.schema_id
    JOIN sys.tables  AS t  ON t.object_id = sp.target_object_id
    JOIN sys.schemas AS ts ON ts.schema_id = t.schema_id
    WHERE ts.name = 'ops' AND t.name LIKE 'rst[_]%' AND sp.predicate_type_desc = 'FILTER';
    IF @sql IS NOT NULL EXEC (@sql);

    IF @drop_tables = 1
    BEGIN
        SET @sql = NULL;
        SELECT @sql = STRING_AGG(CAST('DROP TABLE ops.' + QUOTENAME(t.name) + ';' AS nvarchar(max)), ' ')
        FROM sys.tables AS t
        JOIN sys.schemas AS s ON s.schema_id = t.schema_id
        WHERE s.name = 'ops' AND t.name LIKE 'rst[_]%';
        IF @sql IS NOT NULL EXEC (@sql);
    END
END;
GO

CREATE OR ALTER PROCEDURE ops.usp_restore_table
    @table_name varchar(128),            -- table in schema consumption, or 'ALL'
    @as_of_utc  datetime2(3),            -- UTC point in time to restore to
    @dry_run    bit = 0                  -- 1 = only show current vs. restorable row counts
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @run_id  varchar(36)   = CONVERT(varchar(36), NEWID());
    DECLARE @started datetime2(6)  = SYSUTCDATETIME();
    DECLARE @ts      varchar(30)   = CONVERT(varchar(30), @as_of_utc, 126);
    DECLARE @sql_clone nvarchar(max), @sql_swap nvarchar(max), @sql_cmp nvarchar(max);
    DECLARE @msg varchar(4000);

    IF @as_of_utc >= SYSUTCDATETIME()
        THROW 50010, '@as_of_utc must be in the past.', 1;
    IF @as_of_utc < DATEADD(DAY, -30, SYSUTCDATETIME())
        THROW 50011, '@as_of_utc is outside the 30-day time travel retention.', 1;

    -- Only real tables in schema consumption can be restored (also protects against injection)
    SELECT
        @sql_clone = STRING_AGG(CAST('CREATE TABLE ops.rst_' + t.name + ' AS CLONE OF consumption.' + t.name + ' AT ''' + @ts + ''';' AS nvarchar(max)), ' '),
        @sql_swap  = STRING_AGG(CAST('DELETE FROM consumption.' + t.name + '; INSERT INTO consumption.' + t.name + ' SELECT * FROM ops.rst_' + t.name + ';' AS nvarchar(max)), ' '),
        @sql_cmp   = STRING_AGG(CAST('SELECT ''' + t.name + ''' AS table_name, c.n AS current_rows, r.n AS rows_at_as_of FROM (SELECT COUNT_BIG(*) AS n FROM consumption.' + t.name + ') AS c CROSS JOIN (SELECT COUNT_BIG(*) AS n FROM ops.rst_' + t.name + ') AS r' AS nvarchar(max)), ' UNION ALL ')
    FROM sys.tables AS t
    JOIN sys.schemas AS s ON s.schema_id = t.schema_id
    WHERE s.name = 'consumption' AND (@table_name = 'ALL' OR t.name = @table_name);

    IF @sql_swap IS NULL
        THROW 50012, 'Unknown table. Use a table name from schema consumption or ALL.', 1;

    BEGIN TRY
        -- A filtered user (role_invoice_ltd) would only delete/see part of dim_customer: never run as such a user
        IF IS_ROLEMEMBER('role_invoice_ltd') = 1
            THROW 50013, 'Run the restore as a user that is not a member of role_invoice_ltd (row-level security would hide rows).', 1;

        -- Time travel cannot go back past an ALTER (new column, row-level security policy created/changed/dropped, ...)
        IF EXISTS (SELECT 1 FROM sys.tables AS t JOIN sys.schemas AS s ON s.schema_id = t.schema_id
                   WHERE s.name = 'consumption' AND (@table_name = 'ALL' OR t.name = @table_name)
                     AND t.modify_date > @as_of_utc)
        BEGIN
            SELECT @msg = 'Restore blocked: ' + STRING_AGG(t.name + ' was altered at ' + CONVERT(varchar(23), t.modify_date, 126)
                          + ' UTC', '; ')
                          + ' (schema change or row-level security policy). Choose @as_of_utc after that time, '
                          + 'or reload from gold with pl_load_consumption. Nothing was changed.'
            FROM sys.tables AS t JOIN sys.schemas AS s ON s.schema_id = t.schema_id
            WHERE s.name = 'consumption' AND (@table_name = 'ALL' OR t.name = @table_name)
              AND t.modify_date > @as_of_utc;
            THROW 50014, @msg, 1;
        END

        EXEC ops.usp_clean_restore_clones @drop_tables = 1;
        EXEC (@sql_clone);            -- metadata-only clone of the historical Delta version
        EXEC ops.usp_clean_restore_clones @drop_tables = 0;

        IF @dry_run = 1
        BEGIN
            EXEC (@sql_cmp);
            EXEC ops.usp_clean_restore_clones @drop_tables = 1;
            RETURN;
        END

        BEGIN TRANSACTION;
        EXEC (@sql_swap);
        COMMIT TRANSACTION;

        EXEC ops.usp_clean_restore_clones @drop_tables = 1;
        INSERT INTO ops.load_log (run_id, proc_name, started_utc, finished_utc, status, message)
        VALUES (@run_id, 'ops.usp_restore_table', @started, SYSUTCDATETIME(), 'SUCCEEDED',
                'Restored ' + @table_name + ' to ' + @ts + ' UTC');
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        SET @msg = LEFT(ERROR_MESSAGE(), 4000);
        EXEC ops.usp_clean_restore_clones @drop_tables = 1;
        INSERT INTO ops.load_log (run_id, proc_name, started_utc, finished_utc, status, message)
        VALUES (@run_id, 'ops.usp_restore_table', @started, SYSUTCDATETIME(), 'FAILED', @msg);
        THROW;
    END CATCH
END;
