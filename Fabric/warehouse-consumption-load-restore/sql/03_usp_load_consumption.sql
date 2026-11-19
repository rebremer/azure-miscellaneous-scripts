-- Full-refresh load of the production (consumption) tables in ONE transaction.
-- Readers (snapshot isolation) see either the old or the new data, never an empty/partial table.
-- Any failure (empty source, volume drop, error) rolls everything back and leaves production untouched.
-- Every committed run creates new Delta versions -> ops.load_log.started_utc is the restore point.
CREATE OR ALTER PROCEDURE ops.usp_load_consumption
    @max_drop_pct int = 50   -- abort if a table would shrink by more than this % (0-100)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @run_id  varchar(36)  = CONVERT(varchar(36), NEWID());
    DECLARE @started datetime2(6) = SYSUTCDATETIME();
    DECLARE @today   date         = CAST(SYSUTCDATETIME() AS date);
    DECLARE @msg     varchar(4000);

    BEGIN TRY
        -- A filtered user (role_invoice_ltd) would only delete part of dim_customer and then insert everything: never run as such a user
        IF IS_ROLEMEMBER('role_invoice_ltd') = 1
            THROW 50003, 'Run the load as a user that is not a member of role_invoice_ltd (row-level security would hide rows).', 1;

        -- Guard 1: never wipe production when the source is empty / not yet synced
        IF NOT EXISTS (SELECT 1 FROM lh_gold_shortcuts.dbo.silver_invoice)
           OR NOT EXISTS (SELECT 1 FROM lh_gold_shortcuts.dbo.silver_journal_line)
           OR NOT EXISTS (SELECT 1 FROM lh_gold_shortcuts.dbo.silver_customer)
            THROW 50001, 'Source tables are empty - load aborted, production unchanged.', 1;

        INSERT INTO ops.load_log_table (run_id, table_name, phase, row_count)
        SELECT @run_id, table_name, 'BEFORE', row_count FROM ops.v_table_counts;

        BEGIN TRANSACTION;

        DELETE FROM consumption.agg_gl_balance;
        DELETE FROM consumption.fact_gl_line;
        DELETE FROM consumption.fact_invoice;
        DELETE FROM consumption.dim_fiscal_period;
        DELETE FROM consumption.dim_account;
        DELETE FROM consumption.dim_customer;

        INSERT INTO consumption.dim_customer (customer_id, customer_name, customer_code, country, payment_terms_days)
        SELECT c.customer_id, pii.customer_name, c.customer_code, c.country, c.payment_terms_days
        FROM lh_gold_shortcuts.dbo.silver_customer AS c
        LEFT JOIN lh_gold_shortcuts.dbo.customer_identity AS pii ON pii.customer_id = c.customer_id;

        INSERT INTO consumption.dim_account (account_code, account_name, account_type)
        SELECT account_code, account_name, account_type
        FROM lh_gold_shortcuts.dbo.silver_account;

        INSERT INTO consumption.dim_fiscal_period (period_key, period_start, period_end, fiscal_year, period_number)
        SELECT period_key, period_start, period_end, fiscal_year, period_number
        FROM lh_gold_shortcuts.dbo.silver_fiscal_period;

        INSERT INTO consumption.fact_invoice
            (invoice_id, customer_id, invoice_date, due_date, net_amount, vat_amount, total_amount,
             paid_amount, open_amount, last_payment_date, payment_status)
        SELECT i.invoice_id, i.customer_id, i.invoice_date, i.due_date, i.net_amount, i.vat_amount, i.total_amount,
               COALESCE(p.paid_amount, 0),
               i.total_amount - COALESCE(p.paid_amount, 0),
               p.last_payment_date,
               CASE WHEN COALESCE(p.paid_amount, 0) >= i.total_amount THEN 'Paid'
                    WHEN i.due_date < @today                          THEN 'Overdue'
                    WHEN COALESCE(p.paid_amount, 0) > 0               THEN 'Partially paid'
                    ELSE 'Open' END
        FROM lh_gold_shortcuts.dbo.silver_invoice AS i
        LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid_amount, MAX(payment_date) AS last_payment_date
                   FROM lh_gold_shortcuts.dbo.silver_payment
                   GROUP BY invoice_id) AS p
               ON p.invoice_id = i.invoice_id;

        INSERT INTO consumption.fact_gl_line
            (journal_line_id, journal_id, posting_date, period_key, fiscal_year, period_number, journal_type,
             document_id, account_code, account_name, account_type, customer_id, debit, credit, net_amount)
        SELECT l.journal_line_id, l.journal_id, j.posting_date, j.period_key, fp.fiscal_year, fp.period_number,
               j.journal_type, j.document_id, l.account_code, a.account_name, a.account_type, l.customer_id,
               l.debit, l.credit, COALESCE(l.debit, 0) - COALESCE(l.credit, 0)
        FROM lh_gold_shortcuts.dbo.silver_journal_line AS l
        JOIN lh_gold_shortcuts.dbo.silver_journal      AS j  ON j.journal_id   = l.journal_id
        LEFT JOIN lh_gold_shortcuts.dbo.silver_account       AS a  ON a.account_code = l.account_code
        LEFT JOIN lh_gold_shortcuts.dbo.silver_fiscal_period AS fp ON fp.period_key  = j.period_key;

        INSERT INTO consumption.agg_gl_balance
            (fiscal_year, period_number, account_code, account_name, account_type, debit, credit, balance)
        SELECT fiscal_year, period_number, account_code, account_name, account_type,
               SUM(debit), SUM(credit), SUM(net_amount)
        FROM consumption.fact_gl_line
        GROUP BY fiscal_year, period_number, account_code, account_name, account_type;

        -- Guard 2: abort (and roll back) on a suspicious volume drop
        IF EXISTS (SELECT 1
                   FROM ops.load_log_table AS b
                   JOIN ops.v_table_counts AS a ON a.table_name = b.table_name
                   WHERE b.run_id = @run_id AND b.phase = 'BEFORE'
                     AND b.row_count > 0 AND a.row_count * 100 < b.row_count * (100 - @max_drop_pct))
        BEGIN
            SELECT @msg = 'Volume drop > ' + CAST(@max_drop_pct AS varchar(10)) + '% for: ' +
                          STRING_AGG(b.table_name, ', ')
            FROM ops.load_log_table AS b
            JOIN ops.v_table_counts AS a ON a.table_name = b.table_name
            WHERE b.run_id = @run_id AND b.phase = 'BEFORE'
              AND b.row_count > 0 AND a.row_count * 100 < b.row_count * (100 - @max_drop_pct);
            THROW 50002, @msg, 1;
        END

        COMMIT TRANSACTION;

        INSERT INTO ops.load_log_table (run_id, table_name, phase, row_count)
        SELECT @run_id, table_name, 'AFTER', row_count FROM ops.v_table_counts;
        INSERT INTO ops.load_log (run_id, proc_name, started_utc, finished_utc, status, message)
        VALUES (@run_id, 'ops.usp_load_consumption', @started, SYSUTCDATETIME(), 'SUCCEEDED', NULL);
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        SET @msg = LEFT(ERROR_MESSAGE(), 4000);
        INSERT INTO ops.load_log (run_id, proc_name, started_utc, finished_utc, status, message)
        VALUES (@run_id, 'ops.usp_load_consumption', @started, SYSUTCDATETIME(), 'FAILED', @msg);
        THROW;
    END CATCH
END;
