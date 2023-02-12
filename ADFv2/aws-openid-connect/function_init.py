import logging
import boto3

import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:

    # bearer token passed by ADF webactivity using system assigned MI and resource of app reg that is used as identity provider in AWS
    bearer = req.headers['Authorization'][7:] 
    sts_client = boto3.client('sts')

    # Call the assume_role method of the STSConnection object and pass the role
    # ARN and a role session name.
    response = sts_client.assume_role_with_web_identity(
        RoleArn='arn:aws:iam::<<your aws account>>:role/AzureADWebIdentity3',
        RoleSessionName='app1',
        WebIdentityToken=bearer,
        DurationSeconds=3600
    )

    # From the response that contains the assumed role, get the temporary 
    # credentials that can be used to make subsequent API calls
    credentials=response['Credentials']

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
        logging.info('Python HTTP trigger function processed a request.')

    last_bucket = bucket.name

    return func.HttpResponse(f"Last bucket in AWS: {last_bucket}.")
