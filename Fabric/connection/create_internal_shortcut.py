import requests
import json

# Replace these variables with your specific values
# SPN needs to have 1) rights to read data from target lakehouse (producer) and 2) execute right to create shortut in lakehouse (consumer)
tenant_id = '<<tenant id of SPN>>'
client_id = '<<client id of SPN>>'
client_secret = '<<client secret>>'
# Lakehouse in which the shortcut shall be created
workspace_id = '<<Workspace ID (can be read from browser URL)>>'
item_id = '<<Lakehouse ID (can be read from browser URL)>>'
shortcut_path = 'Tables'
shortcut_name = 'prd1_silver_dimension_customer'
# Lakehouse to which the shortcut shall point to read data
target_workspace_id = '<<Target workspace ID (can be read from browser URL)>>'
target_item_id = '<<Target akeshoue (can be read from browser URL)>>'
target_path = 'Tables/silver_dimension_customer'

# Obtain an Azure AD token
def get_access_token(tenant_id, client_id, client_secret):
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    body = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'https://api.fabric.microsoft.com/.default'
    }
    response = requests.post(url, headers=headers, data=body)
    response.raise_for_status()
    return response.json().get('access_token')

# Create the shortcut
def create_shortcut(access_token, workspace_id, item_id, shortcut_path, shortcut_name, target_workspace_id, target_item_id, target_path):
    url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/{item_id}/shortcuts"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    body = {
        "path": shortcut_path,
        "name": shortcut_name,
        "target": {
            "oneLake": {
                "workspaceId": target_workspace_id,
                "itemId": target_item_id,
                "path": target_path
            }
        }
    }
    response = requests.post(url, headers=headers, data=json.dumps(body))
    response.raise_for_status()
    return response.json()

# Main execution
try:
    token = get_access_token(tenant_id, client_id, client_secret)
    shortcut = create_shortcut(token, workspace_id, item_id, shortcut_path, shortcut_name, target_workspace_id, target_item_id, target_path)
    print("Shortcut created successfully:", shortcut)
except Exception as e:
    print("An error occurred:", e)
