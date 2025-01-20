import requests
import json

# Replace these variables with your specific values
# SPN needs to have 1) User rights to use Fabric connection reading data from ADSLgen2 and 2) execute right to create shortut in lakehouse (producer)
tenant_id = '<<tenant id of SPN>>'
client_id = '<<client id of SPN>>'
client_secret = '<<client secret>>'

# Lakehouse in which the external shortcut shall be created
workspace_id = '<<Workspace ID (can be read from browser URL)>>'
item_id = '<<Lakehouse ID (can be read from browser URL)>>'
shortcut_path = 'Files'
shortcut_name = 'raw'

# ADLSgen2 in which the external shortcut shall be created
target_adls = 'https://<<your storage account>>.dfs.core.windows.net'
target_path = 'producer001/raw'
target_connection_id = '<<your connection id of Fabric Connection to ADLSgen2>>'

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
def create_external_shortcut(access_token, workspace_id, item_id, shortcut_path, shortcut_name, target_adls, target_path, target_connection_id):
    url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/{item_id}/shortcuts"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    body = {
        "path": shortcut_path,
        "name": shortcut_name,
        "target": {
            "adlsGen2": {
                "location": target_adls,
                "subpath": target_path,
                "connectionId": target_connection_id
            }
        }
    }
    response = requests.post(url, headers=headers, data=json.dumps(body))
    response.raise_for_status()
    return response.json()


# Main execution
try:
    token = get_access_token(tenant_id, client_id, client_secret)
    shortcut = create_external_shortcut(token, workspace_id, item_id, shortcut_path, shortcut_name, target_adls, target_path, target_connection_id)
    #lakehouse = create_lakehouse(token, workspace_id, "consp1nlakehouse")
    print("Shortcut created successfully:", shortcut)
except Exception as e:
    print("An error occurred:", e)
