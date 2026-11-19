-- DEMO ONLY: simulate corrupted data in dwh_consumption (customer names filled with gibberish).
-- Touches only the warehouse, not the shared gold lakehouse. Run AFTER a good load.
-- Prints the restore point (UTC, just before the corruption) to use in pl_restore_consumption.

SELECT CONVERT(varchar(19), DATEADD(SECOND, -1, SYSUTCDATETIME()), 126) AS restore_point_utc;

UPDATE consumption.dim_customer
SET customer_name = UPPER(LEFT(REPLACE(CONVERT(varchar(36), NEWID()), '-', ''), 4 + ABS(CHECKSUM(NEWID())) % 12));

SELECT TOP 5 customer_id, customer_code, customer_name FROM consumption.dim_customer ORDER BY customer_id;
