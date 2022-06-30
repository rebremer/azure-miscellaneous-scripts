DECLARE	@return_value nvarchar(4000)
DECLARE @response_sp nvarchar(max)

EXEC	[dbo].[call_adf_pipeline]
		@url = N'https://test-functionmibinding-function.azurewebsites.net/api/HttpTrigger2?code=<<yourcode>>&name=rene',
		@response_rest = @response_sp output;

SELECT * from openjson(@response_sp);

GO
