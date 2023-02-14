
#import boto3

#from azure.keyvault.secrets import SecretClient
#from azure.identity import DefaultAzureCredential

import logging
import azure.functions as func

def main(req: func.HttpRequest) -> func.HttpResponse:

    logging.info('Python HTTP trigger function processed a request.')
    return func.HttpResponse(req.headers['Authorization'])
    #keyVaultName = "test-awsadf-akv" #os.environ["KEY_VAULT_NAME"]
    #bearer = req.headers['Authorization'][7:]
    

    #sts_client = boto3.client('sts')

    # Call the assume_role method of the STSConnection object and pass the role
    # ARN and a role session name.
    #response = sts_client.assume_role_with_web_identity(
    #    RoleArn='arn:aws:iam::<<your aws account>>:role/AzureADWebIdentity3',
    #    RoleSessionName='app1',
    #    WebIdentityToken=bearer,
    #    DurationSeconds=3600
    #)

    # From the response that contains the assumed role, get the temporary 
    # credentials that can be used to make subsequent API calls
    #aws_temp_credentials=response['Credentials']

    #KVUri = f"https://{keyVaultName}.vault.azure.net"

    #credential = DefaultAzureCredential()
    #client = SecretClient(vault_url=KVUri, credential=credential)

    #logging.info('Write temp AWS keys to key vault')
    #client.set_secret("adf-test-aws-aws-accesskeyid", aws_temp_credentials['AccessKeyId'])
    #client.set_secret("adf-test-aws-aws-secretaccesskey", aws_temp_credentials['SecretAccessKey'])
    #client.set_secret("adf-test-aws-aws-sessiontoken", aws_temp_credentials['SessionToken'])

    #return func.HttpResponse(f"temp AWS keys succesfully writen to key vault")

    # Use the temporary credentials that AssumeRole returns to make a 
    # connection to Amazon S3  
    # s3_resource=boto3.resource(
    #    's3',
    #    aws_access_key_id=credentials['AccessKeyId'],
    #    aws_secret_access_key=credentials['SecretAccessKey'],
    #    aws_session_token=credentials['SessionToken'],
    #)

    # Use the Amazon S3 resource object that is now configured with the 
    # credentials to access your S3 buckets. 
    # for bucket in s3_resource.buckets.all():
    ##   print(bucket.name)
    #    last_bucket = bucket.name

    # return func.HttpResponse(f"Last bucket in AWS: {last_bucket}.")
