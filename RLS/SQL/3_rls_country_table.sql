-- 1. Security schema
CREATE SCHEMA Security;
GO

-- 2. Inline TVF used as RLS predicate
CREATE OR ALTER FUNCTION Security.fn_employee_country_rls
(
    @Country CHAR(2)
)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN
(
    SELECT 1 AS allowed
    WHERE
        ----------------------------------------------------------------
        -- ADMIN OVERRIDE (always allow)
        ----------------------------------------------------------------
        IS_ROLEMEMBER('db_owner') = 1
        OR USER_NAME() = 'dbo'

        ----------------------------------------------------------------
        -- Full access Entra group
        ----------------------------------------------------------------
        OR IS_MEMBER('Employee_all') = 1

        ----------------------------------------------------------------
        -- Country‑specific Entra groups
        ----------------------------------------------------------------
        OR (IS_MEMBER('Employee_US') = 1 AND @Country = 'US')
        OR (IS_MEMBER('Employee_IN') = 1 AND @Country = 'IN')
        OR (IS_MEMBER('Employee_GB') = 1 AND @Country = 'GB')
);
GO

-- 3. Attach RLS policy to the table
CREATE SECURITY POLICY Security.EmployeeCountryPolicy
ADD FILTER PREDICATE Security.fn_employee_country_rls(Country)
ON dbo.Employee
WITH (STATE = ON);
GO

-- ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
-- ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

DROP SECURITY POLICY [Security].EmployeeCountryPolicy;

DROP FUNCTION IF EXISTS [Security].[fn_employee_country_rls]
GO
