-- Row counts of all production tables (used by the load guard and audit log).
CREATE OR ALTER VIEW ops.v_table_counts AS
SELECT 'dim_customer'      AS table_name, COUNT_BIG(*) AS row_count FROM consumption.dim_customer
UNION ALL SELECT 'dim_account',       COUNT_BIG(*) FROM consumption.dim_account
UNION ALL SELECT 'dim_fiscal_period', COUNT_BIG(*) FROM consumption.dim_fiscal_period
UNION ALL SELECT 'fact_invoice',      COUNT_BIG(*) FROM consumption.fact_invoice
UNION ALL SELECT 'fact_gl_line',      COUNT_BIG(*) FROM consumption.fact_gl_line
UNION ALL SELECT 'agg_gl_balance',    COUNT_BIG(*) FROM consumption.agg_gl_balance;
