INSERT INTO [dbo].[movies_version]
SELECT [movie], 
	  (ROW_NUMBER() OVER (PARTITION By movie ORDER BY movie)  -1 ) as versionrbr
      ,  DATEADD(day,  (ROW_NUMBER() OVER (PARTITION By movie ORDER BY movie) - 1), CAST( GETDATE() AS Date ))
	  ,[title]
      ,[genres]
      ,[year]
      ,ABS(CHECKSUM(NewId())) % 101
      ,ABS(CHECKSUM(NewId())) % 101
  FROM [dbo].[movies]
order by movie
