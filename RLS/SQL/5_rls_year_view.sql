CREATE OR ALTER FUNCTION Security.fn_employee_latest_year_rls
(
    @StartYear INT
)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN
(
    SELECT 1 AS allowed
    WHERE 
    
        IS_ROLEMEMBER('db_owner') = 1
        OR USER_NAME() = 'dbo'

        ----------------------------------------------------------------
        -- Full access Entra group
        ----------------------------------------------------------------
        OR IS_MEMBER('Employee_all') = 1
        OR @StartYear = 2017 AND (IS_MEMBER('Employee_US') = 1 OR IS_MEMBER('Employee_IN') = 1 OR IS_MEMBER('Employee_GB') = 1)       
);

CREATE SECURITY POLICY Security.EmployeeYearPolicy
ADD FILTER PREDICATE Security.fn_employee_latest_year_rls(StartYear)
ON dbo.vw_Employee_Holidays
WITH (STATE = ON);