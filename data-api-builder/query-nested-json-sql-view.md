## JSON in SQL table exposed as view to query using Data API Builder

Based on tutorial here: https://learn.microsoft.com/en-us/azure/data-api-builder/quickstart-sql

### 1. Create tables in SQL

```sql
DROP TABLE IF EXISTS dbo.transformator;
GO

CREATE TABLE dbo.transformator
(
    id int not null primary key,
    naam nvarchar(100) null,
    gemeente nvarchar(100) not null,
	locatie json not null
)
GO

INSERT INTO dbo.transformator VALUES
  (1, 'test1', 'Utrecht', '{"latlon": {"lat": 4, "lon":5}}')
  (2, 'test2', 'Amersfoort', '{"latlon": {"lat": 6, "lon":7}}')
GO

DROP VIEW IF EXISTS dbo.transformator_view;
GO

CREATE VIEW dbo.transformator_view
AS
(
	SELECT id, naam, gemeente, locatie,
	CAST(JSON_VALUE(locatie, '$.latlon.lat') AS INT) AS locatie_latlon_lat,
	CAST(JSON_VALUE(locatie, '$.latlon.lon') AS INT) AS locatie_latlon_lon
	FROM  dbo.transformator 
)
GO
```

### 2. Create DAB config file

dab init --database-type "mssql" --host-mode "Development" --connection-string "Server=<<your sql server>>.database.windows.net,1433;User Id=<<your id>>;Database=test-dab-db;Password=<<your password>>;TrustServerCertificate=True;Encrypt=True;"
dab add Transformator --source "dbo.transformator_view" --permissions "anonymous:*"

### 3. Query DAB using following URL

http://localhost:5000/api/Transformator?$filter=locatie_latlon_lat eq 4

### 4. Result

{
  "value": [
    {
      "id": 1,
      "naam": "test1",
      "gemeente": "Utrecht",
      "locatie": {
        "latlon": {
          "lat": 4,
          "lon": 5
        }
      },
      "locatie_latlon_lat": 4,
      "locatie_latlon_lon": 5
    }
  ]
}
