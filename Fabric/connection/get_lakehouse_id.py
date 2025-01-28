import requests
import json

# Replace with your actual workspace ID and token
workspace_id = "your_workspace_id"
token = "your_access_token"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

response = requests.get(f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/lakehouses", headers=headers)
lakehouses = response.json()["value"]

# Replace 'your_lakehouse_name' with the actual name of the lakehouse
lakehouse_name = "your_lakehouse_name"
lakehouse = next((item for item in lakehouses if item["displayName"] == lakehouse_name), None)

if lakehouse:
    print(f"Found lakehouse: {lakehouse['id']}")
else:
    print("Lakehouse not found.")
