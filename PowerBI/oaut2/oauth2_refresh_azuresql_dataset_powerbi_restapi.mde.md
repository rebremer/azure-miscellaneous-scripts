## Script to update Oauth2 token from Azure SQL dataset using PowerBI rest API:

### step 1: Create bearer1 to be able to communicatie with Power BI REST API (PowerShell):

```Connect-PowerBIServiceAccount```
```$bearer1= Get-PowerBIAccessToken -AsString```

### step 2: Create bearer2 to be able to communicatie with Azure SQL (Azure CLI)

```$bearer2 = (Get-AzAccessToken -ResourceUrl 'https://database.windows.net/').Token```

(or via Azure CLI):

```az account get-access-token --resource https://database.windows.net/)```

### step 3: Substitute bearer tokens and gateway id/dataset id and run following curl command

```
curl --location --request PATCH 'https://api.powerbi.com/v1.0/myorg/gateways/<<your gateway id>> /datasources/<<your dataset id>>' \
--header 'Authorization: Bearer <<bearer1>>' \
--header 'Content-Type: application/json' \
--data '{
  "credentialDetails": {
    "credentialType": "OAuth2",
    "credentials": "{\"credentialData\":[{\"name\":\"accessToken\", \"value\":\"<<bearer2>> \"}]}",
    "encryptedConnection": "Encrypted",
    "encryptionAlgorithm": "None",
    "privacyLevel": "None"
  }
}'
```
