import boto3

# The calls to AWS STS AssumeRole must be signed with the access key ID
# and secret access key of an existing IAM user or by using existing temporary 
# credentials such as those from another role. (You cannot call AssumeRole 
# with the access key for the root account.) The credentials can be in 
# environment variables or in a configuration file and will be discovered 
# automatically by the boto3.client() function. For more information, see the 
# Python SDK documentation: 
# http://boto3.readthedocs.io/en/latest/reference/services/sts.html#client
#
# https://www.filestash.app/2021/09/12/use-role-in-aws-s3/#access-s3-with-temporary-credentials
# https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sts.html#STS.Client.assume_role_with_web_identity
#
# create an STS client object that represents a live connection to the 
# STS service
sts_client = boto3.client('sts')
#print("rene")

# Call the assume_role method of the STSConnection object and pass the role
# ARN and a role session name.
response = sts_client.assume_role_with_web_identity(
    RoleArn='arn:aws:iam::<<your AWS id>>:role/AzureADWebIdentity3',
    RoleSessionName='app1',
    WebIdentityToken='<<token generated in ADF web activity using resource of app reg>>',
    DurationSeconds=3600
)

#sts.windows.net/594ef155-b5f1-4381-9218-2ea93f0645f2

# From the response that contains the assumed role, get the temporary 
# credentials that can be used to make subsequent API calls
credentials=response['Credentials']
print(str(credentials['AccessKeyId']))

# Use the temporary credentials that AssumeRole returns to make a 
# connection to Amazon S3  
s3_resource=boto3.resource(
    's3',
    aws_access_key_id=credentials['AccessKeyId'],
    aws_secret_access_key=credentials['SecretAccessKey'],
    aws_session_token=credentials['SessionToken'],
)

# Use the Amazon S3 resource object that is now configured with the 
# credentials to access your S3 buckets. 
for bucket in s3_resource.buckets.all():
    print(bucket.name)
