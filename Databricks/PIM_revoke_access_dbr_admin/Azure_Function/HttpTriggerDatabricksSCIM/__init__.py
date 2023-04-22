import logging
import azure.functions as func
from azure.identity import DefaultAzureCredential
import requests
import os

# In case no MI is used, add AZURE_TENANT_ID, AZURE_CLIENT_ID and AZURE_CLIENT_SECRET to environment variables

def main(req: func.HttpRequest) -> func.HttpResponse:

    logging.info('Alert was created that someone was removed as Contributor on Databricks workspace, user now need to be deleted as Databricks admin. ')
    body = req.get_json()
    #logging.info(body)  
    #
    token_credential = DefaultAzureCredential()
    dbr_bearer = token_credential.get_token("2ff814a6-3304-4ab8-85cb-cd0e6f879c1d/.default").token
    dbr_az_token = token_credential.get_token("https://management.core.windows.net//.default").token
    databricks_api = os.environ["databricks_api"]
    databricks_id = os.environ["databricks_id"]
    #
    # Find Object ID of user that was removed as Contributor on Databricks workspace in log query
    for query in body["data"]["alertContext"]["condition"]["allOf"]:
        for dimension in query["dimensions"]:   
            if dimension["name"] == "json_cleansed_props_responseBody_properties_principalId":
                input_principal_id = dimension["value"]
                logging.info('input_principal_id: ' + str(input_principal_id))       
            else:
                # no ID present, break loop
                break 

            # Get Databricks internal user ID using object ID
            response = requests.get(f"{databricks_api}/api/2.0/preview/scim/v2/Users?filter=externalId+eq+" + input_principal_id,
                headers= {
                    "Accept": "application/scim+json",
                    "Authorization": "Bearer " + dbr_bearer,
                    "X-Databricks-Azure-SP-Management-Token": dbr_az_token,
                    "X-Databricks-Azure-Workspace-Resource-Id" : databricks_id
                }
            )
            resources = response.json().get('Resources')
            # No need to iterate, object id is unique and 0 or 1 records are returned
            if resources != None:
                databricks_internal_id = resources[0]['id']
                # Databricks internal user ID is found, delete user as Databricks user
                response = requests.delete(f"{databricks_api}/api/2.0/preview/scim/v2/Users/" + databricks_internal_id,
                    headers= {
                        "Accept": "application/scim+json",
                        "Authorization": "Bearer " + dbr_bearer,
                        "X-Databricks-Azure-SP-Management-Token": dbr_az_token,
                        "X-Databricks-Azure-Workspace-Resource-Id" : databricks_id
                    }
                )

            logging.info('input_principal_id: ' + str(input_principal_id) + ' was deleted as Databricks admin')

    return func.HttpResponse(
        "Users deleted",
        status_code=response.status_code
    )