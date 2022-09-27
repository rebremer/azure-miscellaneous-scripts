/****** Object:  Table [dbo].[movies_int]    Script Date: 9/27/2022 8:54:12 AM ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

DROP TABLE [dbo].[movies_version]

CREATE TABLE [dbo].[movies_version](
	[movie] [int] NULL,
	[version] [int] NULL,
	[update_time] [date] NULL,
	[title] [nvarchar](max) NULL,
	[genres] [nvarchar](max) NULL,
	[year] [nvarchar](max) NULL,
	[Rating] [nvarchar](max) NULL,
	[Rotten_tomato] [nvarchar](max) NULL,
	[description] [nvarchar](max)
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO


INSERT INTO [dbo].[movies_version]
SELECT [movie], 
	  (ROW_NUMBER() OVER (PARTITION By movie ORDER BY movie)  -1 ) as versionrbr
      ,  DATEADD(day,  (ROW_NUMBER() OVER (PARTITION By movie ORDER BY movie) - 1), CAST( GETDATE() AS Date ))
	  ,[title]
      ,[genres]
      ,[year]
      ,ABS(CHECKSUM(NewId())) % 101
      ,ABS(CHECKSUM(NewId())) % 101
	  , CONVERT(nvarchar(max), CONCAT(NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID(),NEWID(), NEWID()))
  FROM [dbo].[movies]
