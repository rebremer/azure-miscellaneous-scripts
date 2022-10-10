1. Create tables with movies.sql in Azure SQL database
2. Insert movies.csv into sql table
3. Run movies_description.sql in Azure SQL database (make sure 50 DTUs or more are used in Azure SQL)
4. Create ADF pipeline and dataflows. Overwrite pipeline and dataflows with content of pipeline.json and dataflows.json
5. Create new linked services and new datasets that are referred to in pipeline and dataflows
6. Run pipeline (end result should be 100.000 small files on the storage account)
