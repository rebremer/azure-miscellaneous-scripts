# Databricks notebook source
# MAGIC %md
# MAGIC # Bulk Assign Glossary Terms to Assets
# MAGIC 
# MAGIC **Description**
# MAGIC - This notebook will create a CSV file using a top level guid (e.g. sql server, storage acount) which has a list of entities mapped to a glossary term.
# MAGIC - The notebook will then loop through each term and bulk assign the entities.
# MAGIC - Notebook runs on Databricks, no need to setup op Python or venv locally
# MAGIC Notebook has not Spark dependencies, plain python is used (no pyspark)

# COMMAND ----------

# ENVIRONMENT VARIABLES

# 1. Update PURVIEW_NAME with your Purview account name. DON'T USE QUOTATIONS!!!
%env PURVIEW_NAME=<<your purview name without quotations>>
# 2. Uncomment and set the variables below if you plan to use a Service Principal. DON'T USE QUOTATIONS!!!
# Make sure that Service Principal is data curator in Purview minimally
%env AZURE_CLIENT_ID=<<your client id without quotations>>
%env AZURE_TENANT_ID=<<your tenant id without quotations>>
%env AZURE_CLIENT_SECRET=<<your client secreat without quotations>>

# Secrets shall never be stored in plain text. Instead, use Databricks secret scope, see https://learn.microsoft.com/en-us/azure/databricks/security/secrets/secret-scopes

 COMMAND ----------

# MAGIC %sh
# MAGIC pip install purviewcli

# COMMAND ----------

import json
def getJSON(raw_output):
  output = ''.join(raw_output)
  json_obj = json.loads(output)
  return json_obj

# COMMAND ----------

assets = !pv search query --keywords "*" --limit 1000
assets_json = getJSON(assets)
#print(assets_json)
files_list = []
for value in assets_json["value"]:
    if "entityType" in value:
        if value["entityType"] == "azure_datalake_gen2_path" and value["objectType"] == "Files":
            qualifiedName_no_spaces = value["qualifiedName"].replace(" ", "%20")
            files_list.append(qualifiedName_no_spaces)

print(files_list)

# COMMAND ----------

guid_file_list = []
nummer = 0
for file in files_list:
    assets = !pv entity readBulkUniqueAttribute --typeName="azure_datalake_gen2_path" --qualifiedName={file}
    if assets[0] != "[INFO] No data returned in the response.":
        assets_json = getJSON(assets)
        for asset in assets_json["entities"]:
            if len(asset["relationshipAttributes"]["attachedSchema"]) > 0:
                guid = asset["relationshipAttributes"]["attachedSchema"][0]["guid"]
                guid_file_list.append(guid)

print(guid_file_list)

# COMMAND ----------

# 2. Get Glossary
# make sure SPN is data curator in Purview data plane
guid_glossary_list = []

glossary = !pv glossary read
glossary_json = getJSON(glossary)
for glossary in glossary_json:
    for term in glossary["terms"]:
        term_item = {"displayText": term["displayText"], "termGuid": term["termGuid"]}
        guid_glossary_list.append(term_item)

print(guid_glossary_list)

# COMMAND ----------

import purviewcli as pv

for guid_glossary in guid_glossary_list:
    payload = []
    for guid_file in guid_file_list:

        assets = !pv entity read --guid {guid_file}
        assets_json = getJSON(assets)
        for column in assets_json["entity"]["relationshipAttributes"]["columns"]:
            if guid_glossary["displayText"].replace(" ", "").lower() == column["displayText"].lower():
                itemGuid = {"guid": column["guid"]}
                payload.append(itemGuid)
                print(itemGuid)
                print(assets_json["entity"]["attributes"]["qualifiedName"])
                print(guid_glossary["displayText"])

    if len(payload) > 0:
        with open("payload.json", "w") as outfile:
            json.dump(payload, outfile, indent=4, sort_keys=False)

        !pv glossary createTermsAssignedEntities --termGuid {guid_glossary["termGuid"]} --payloadFile "payload.json"

# COMMAND ----------

# MAGIC %sh
# MAGIC cat payload.json

# COMMAND ----------
