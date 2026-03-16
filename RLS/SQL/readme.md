### Scripts to demonstrate how to use Row Level Security (RLS) in Azure SQL. 

Scripts in repo do the following:

- 1_init_tables.sql: Create tables and view in default dbo schema (this schema is automatically created once you deploy an Azure SQL DB)
- 2_init_users.sql: Create groups ins SQL and grants roles (groups and users need to be assigned in MSFT entra)
- 3_rls_country.sql: Create RLS on tables created in step 1
- 4_rls_year_view.sql: Create RLS on view created in step 1
- 5_rls_year_view.sql: Login in as user of Employee_US group and demonstrate 1) how RLS is applied on tables, 2) how RLS on tables are propagated to the view and 3) how new RLS rules can be applied on the view itself 
