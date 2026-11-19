-- Invoice access for members of Entra group ad_group_invoice_LTD: they only see customers (and therefore invoices) whose name ends with LTD.
-- Row-level security sits on the BASE TABLE that holds the name: consumption.dim_customer (policy sec.pol_invoice_ltd).
-- consumption.v_invoice is a plain view (no policy); it joins fact_invoice with dim_customer, so invoices of customers
-- that the caller may not see drop out of the result.
-- Members of role_invoice_ltd are filtered; everyone else (loader/pipeline owner, admins, other roles) is unfiltered.
-- The comparison is case-insensitive on purpose: names end in 'Ltd' and the warehouse collation is case-sensitive (BIN2).
-- Adding the Entra group to the role is a separate step: role_members_manual.sql.
--
-- WARNING: creating, changing or dropping the policy is an ALTER of consumption.dim_customer. Time travel cannot go back past an
-- ALTER, so ops.usp_restore_table refuses restore points before it (see README). Objects below are only created when missing,
-- so re-running this script does not touch the table. To change the rule: drop the policy and function, then re-create (plan it).

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = 'role_invoice_ltd' AND type = 'R')
    CREATE ROLE role_invoice_ltd;
GO

IF SCHEMA_ID('sec') IS NULL EXEC('CREATE SCHEMA sec');
GO

-- Migration: an earlier version put the policy on the view (or on fact_invoice); remove it.
IF EXISTS (SELECT 1 FROM sys.security_predicates AS sp
           JOIN sys.security_policies AS p ON p.object_id = sp.object_id
           WHERE p.name = 'pol_invoice_ltd' AND sp.target_object_id <> OBJECT_ID('consumption.dim_customer'))
    DROP SECURITY POLICY sec.pol_invoice_ltd;
GO

CREATE OR ALTER VIEW consumption.v_invoice AS
SELECT i.invoice_id, i.customer_id, c.customer_code, c.customer_name, c.country,
       i.invoice_date, i.due_date, i.net_amount, i.vat_amount, i.total_amount,
       i.paid_amount, i.open_amount, i.last_payment_date, i.payment_status
FROM consumption.fact_invoice AS i
JOIN consumption.dim_customer AS c ON c.customer_id = i.customer_id;
GO

IF OBJECT_ID('sec.fn_invoice_ltd_filter') IS NULL
    EXEC('CREATE FUNCTION sec.fn_invoice_ltd_filter(@customer_name varchar(200))
          RETURNS TABLE
          WITH SCHEMABINDING
          AS RETURN
              SELECT 1 AS allowed
              WHERE IS_ROLEMEMBER(''role_invoice_ltd'') = 0
                 OR UPPER(@customer_name) LIKE ''%LTD''');
GO

IF NOT EXISTS (SELECT 1 FROM sys.security_policies WHERE name = 'pol_invoice_ltd')
    CREATE SECURITY POLICY sec.pol_invoice_ltd
        ADD FILTER PREDICATE sec.fn_invoice_ltd_filter(customer_name) ON consumption.dim_customer
        WITH (STATE = ON);
GO

GRANT SELECT ON consumption.v_invoice TO role_invoice_ltd;
