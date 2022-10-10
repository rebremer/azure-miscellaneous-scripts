# ADF/Spark small files demo:

## Create SQL data
1. Create tables with dbo.movies.sql in an Azure SQL database
2. Insert dbo.movies.txt into sql table (e.g. using SSMS or ADF)
3. Run dbo.movies_version.sql in Azure SQL database (make sure 50 DTUs or more are used in Azure SQL). Script can take more than 1 hour.

## Create ADF pipeline
4. Create a new ADF pipeline named "38_1_small_files_delta_lake" and new dataflows named "Delta_lake_producer_small_files"
5. Overwrite pipeline and dataflows with content of 38_1_small_files_delta_lake.json and Delta_lake_producer_small_files.json
6. Create an ADLSgen2 storage account with HNS enabled, create a file_system "deltalakeproducer", folder "moviedata" and a subfolder "smallfiles" 
7. Create new linked services and new datasets that are referred to in pipeline and dataflows and point to a storage account created in step 6.
8. Grant ADF managed identity "Storage Blob Data Contributor" rights on storage account
9. Run pipeline (end result should be 100.000 small files on the storage account). See also smallfiles.png

## Run queries via Databricks and Synapse
10. Mount storage account to Databricks, import notebook "Databricks_query_data_delta_lake.ipynb" and run notebook
11. Grant Synapse MI "Storage Blob Data Contributor" rights on storage account, import notebook "Synapse_query_data_delta_lake.ipynb" and run notebook
