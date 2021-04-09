/****** Object:  StoredProcedure [dbo].[sp_doSourceSinkColumnMapping]    Script Date: 4/9/2021 1:06:49 PM ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE   PROCEDURE [dbo].[sp_doSourceSinkColumnMapping]
  @input_json VARCHAR(MAX),
  @table_name VARCHAR(100)
AS
BEGIN

  SET @input_json = REPLACE(@input_json,'\', '')
  DECLARE @json_construct varchar(MAX)
  DECLARE @json_end varchar(MAX) = N'{"type": "TabularTranslator", "mappings": {X}}';
  SET @json_construct = (
    SELECT ua.value AS 'source', c.name AS 'sink.name'  FROM sys.columns c
      INNER JOIN sys.objects AS o on c.object_id=o.object_id AND o.name = @table_name
      INNER JOIN openjson(@input_json) AS ua on c.column_id = ua.[key] + 1
    ORDER BY c.column_id ASC
  FOR JSON PATH
  )

  SET @json_construct = REPLACE(@json_construct,'\', '')
  SET @json_construct = REPLACE(@json_construct,'"{', '{')
  SET @json_construct = REPLACE(@json_construct,'}"', '}')

  SELECT REPLACE(@json_end,'{X}', @json_construct) AS json_output;
  --SELECT @input_json AS json_output;
END
GO