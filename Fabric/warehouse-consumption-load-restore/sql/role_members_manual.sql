-- Add the Entra group to the role. Run after the group exists in the tenant (and has access to the workspace/warehouse).
-- Members see consumption.v_invoice with only the invoices of customers whose name ends with LTD (policy sec.pol_invoice_ltd).
ALTER ROLE role_invoice_ltd ADD MEMBER [ad_group_invoice_LTD];
