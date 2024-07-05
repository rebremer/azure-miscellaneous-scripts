import requests
import json


# az account get-access-token --resource https://analysis.windows.net/powerbi/api

url ="https://api.powerbi.com/v2.0/myorg/me/gatewayClusterCloudDatasource"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer xyz"
}

# Define the JSON payload
payload = {
    "datasourceName": "testtest",
    "datasourceType": "AzureDataLakeStorage",
    "connectionDetails": "{\"server\":\"https://xyz.dfs.core.windows.net/\",\"path\":\"p004standardized\"}",
    "singleSignOnType": "None",
    "credentialDetails": {
        "credentialType": "ServicePrincipal",
        "credentials": "{\"credentialData\":[{\"name\":\"tenantId\",\"value\":\"xyz\"},{\"name\":\"servicePrincipalClientId\",\"value\":\"xyz\"},{\"name\":\"servicePrincipalSecret\",\"value\":\"xyz\"}]}",
        "encryptedConnection": "Any",
        "privacyLevel": "Organizational",
        "skipTestConnection": False,
        "encryptionAlgorithm": "NONE"
    },
    "allowDatasourceThroughGateway": False
}

# Make the POST request
response = requests.post(url, headers=headers, json=payload)

# Check if the request was successful
if response.status_code == 200:
    print("Request successful.")
else:
    print(f"Request failed with status code: {response.status_code}")
    print("Response:", response.text)
