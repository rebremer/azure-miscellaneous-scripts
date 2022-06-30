GO

SET QUOTED_IDENTIFIER ON

CREATE PROCEDURE [dbo].[call_adf_pipeline]
(
 @url nvarchar(4000),
 @response_rest nvarchar(max) output
)

AS

BEGIN
	DECLARE @payload nvarchar(max) = N'';
	DECLARE @headers nvarchar(4000) = N'';
	DECLARE @ret int

	EXEC @ret = sys.sp_invoke_external_rest_endpoint 
		 @method = 'POST',
		 @url = @url,
		 @response = @response_rest output;

	Return
END
GO
