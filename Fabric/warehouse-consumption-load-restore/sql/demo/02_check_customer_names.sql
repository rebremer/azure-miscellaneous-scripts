-- DEMO ONLY: compare dwh_consumption customer names with the gold lakehouse (source of truth).
SELECT COUNT(*) AS customers,
       SUM(CASE WHEN d.customer_name = s.customer_name THEN 0 ELSE 1 END) AS names_differing_from_gold
FROM consumption.dim_customer AS d
LEFT JOIN lh_gold_shortcuts.dbo.customer_identity AS s ON s.customer_id = d.customer_id;

SELECT TOP 5 d.customer_id, d.customer_name AS dwh_name, s.customer_name AS gold_name
FROM consumption.dim_customer AS d
LEFT JOIN lh_gold_shortcuts.dbo.customer_identity AS s ON s.customer_id = d.customer_id
ORDER BY d.customer_id;
