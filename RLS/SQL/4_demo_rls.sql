SELECT
    IS_MEMBER('Employee_all')  AS IsAll,
    IS_MEMBER('Employee_US')  AS IsUS,
    IS_MEMBER('Employee_IN')  AS IsIN,
    IS_MEMBER('Employee_GB')  AS IsGB;

SELECT TOP (1000) [EmployeeID]
      ,[Name]
      ,[Country]
      ,[StartYear]
  FROM [dbo].[Employee]

SELECT * FROM dbo.vw_Employee_Holidays