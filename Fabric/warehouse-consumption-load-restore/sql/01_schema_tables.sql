-- Consumption warehouse (dwh_consumption) - schemas and production tables.
-- Source: lakehouse lh_gold_shortcuts (same workspace) via its SQL analytics endpoint.
-- PII (customer_identity) is intentionally NOT copied into the warehouse.

IF SCHEMA_ID('consumption') IS NULL EXEC('CREATE SCHEMA consumption');
IF SCHEMA_ID('ops') IS NULL EXEC('CREATE SCHEMA ops');

IF OBJECT_ID('ops.load_log') IS NULL
CREATE TABLE ops.load_log
(
    run_id          varchar(36)   NOT NULL,
    proc_name       varchar(128)  NOT NULL,
    started_utc     datetime2(6)  NOT NULL,  -- use as restore point: state BEFORE this run
    finished_utc    datetime2(6)  NULL,
    status          varchar(20)   NOT NULL,  -- SUCCEEDED | FAILED
    message         varchar(4000) NULL
);

IF OBJECT_ID('ops.load_log_table') IS NULL
CREATE TABLE ops.load_log_table
(
    run_id       varchar(36)  NOT NULL,
    table_name   varchar(128) NOT NULL,
    phase        varchar(10)  NOT NULL,  -- BEFORE | AFTER
    row_count    bigint       NULL
);

IF OBJECT_ID('consumption.dim_customer') IS NULL
CREATE TABLE consumption.dim_customer
(
    customer_id         int          NOT NULL,
    customer_code       varchar(100) NULL,
    country             varchar(100) NULL,
    payment_terms_days  int          NULL
);

-- Only customer_name is taken from the restricted PII table; email/contact_name stay out of the DWH.
IF NOT EXISTS (SELECT 1 FROM sys.columns WHERE object_id = OBJECT_ID('consumption.dim_customer') AND name = 'customer_name')
    ALTER TABLE consumption.dim_customer ADD customer_name varchar(200) NULL;

IF OBJECT_ID('consumption.dim_account') IS NULL
CREATE TABLE consumption.dim_account
(
    account_code  varchar(50)  NOT NULL,
    account_name  varchar(200) NULL,
    account_type  varchar(50)  NULL
);

IF OBJECT_ID('consumption.dim_fiscal_period') IS NULL
CREATE TABLE consumption.dim_fiscal_period
(
    period_key    int  NOT NULL,
    period_start  date NULL,
    period_end    date NULL,
    fiscal_year   int  NULL,
    period_number int  NULL
);

IF OBJECT_ID('consumption.fact_invoice') IS NULL
CREATE TABLE consumption.fact_invoice
(
    invoice_id         int           NOT NULL,
    customer_id        int           NULL,
    invoice_date       date          NULL,
    due_date           date          NULL,
    net_amount         decimal(18,2) NULL,
    vat_amount         decimal(18,2) NULL,
    total_amount       decimal(18,2) NULL,
    paid_amount        decimal(18,2) NULL,
    open_amount        decimal(18,2) NULL,
    last_payment_date  date          NULL,
    payment_status     varchar(20)   NULL  -- Paid | Partially paid | Open | Overdue (as of load date)
);

IF OBJECT_ID('consumption.fact_gl_line') IS NULL
CREATE TABLE consumption.fact_gl_line
(
    journal_line_id  int           NOT NULL,
    journal_id       int           NULL,
    posting_date     date          NULL,
    period_key       int           NULL,
    fiscal_year      int           NULL,
    period_number    int           NULL,
    journal_type     varchar(50)   NULL,
    document_id      int           NULL,
    account_code     varchar(50)   NULL,
    account_name     varchar(200)  NULL,
    account_type     varchar(50)   NULL,
    customer_id      int           NULL,
    debit            decimal(18,2) NULL,
    credit           decimal(18,2) NULL,
    net_amount       decimal(18,2) NULL  -- debit - credit
);

IF OBJECT_ID('consumption.agg_gl_balance') IS NULL
CREATE TABLE consumption.agg_gl_balance
(
    fiscal_year    int           NULL,
    period_number  int           NULL,
    account_code   varchar(50)   NULL,
    account_name   varchar(200)  NULL,
    account_type   varchar(50)   NULL,
    debit          decimal(18,2) NULL,
    credit         decimal(18,2) NULL,
    balance        decimal(18,2) NULL
);
