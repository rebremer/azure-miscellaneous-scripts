# Project that enables to do dynamic mapping from csv files in tables in single pipeline

In this, mapping is based on position, e.g.

- CSV file 1 with ```voornaam, achternaam, leeftijd``` will be written to Table 1 as ```firstname, lastname, age```
- CSV file 2 with ```IBAN1, price, price1, price2``` will be written to Table 2 as ```IBAN, price, SalesPrice, PurchasePrice```

This project owns to following blog: https://sqlitybi.com/dynamically-set-copy-activity-mappings-in-azure-data-factory-v2/?doing_wp_cron=1617948385.9531490802764892578125

## Pipeline is created as follows:
- Use For each to loop to add file 1..N to table 1..N using array parameter where source files/sink tables are specified 
- Use Get Metadata activity to get the csv file structure
- Pass file structure of csv and tablename to stored procedure. Stored procedure creates mapping between csv file structure and table columns based on position
- Use dynamic mapping in sink mapping to write csv file data to table

See als picture below

![pipeline](/_ExampleData/dynamicmappingpipeline.png)

## Steps to execute:
- clone this git repository, create a new Azure Data Factory instance and import the git
- Create SQLDB, Storage account and make sure Azure Data Factory can access storage and SQLDB
- Add csv files in _ExampleData to storage account, create tables in _ExampleData in SQLDB
- Create sp_doSourceSinkColumnMapping.sql in your SQLDB. This is where the heavy lifting is done.
