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
# 0.1 load env variables
# 1. Update PURVIEW_NAME with your Purview account name. DON'T USE QUOTATIONS!!!
%env PURVIEW_NAME=<<your purview name without quotations>>
# 2. Uncomment and set the variables below if you plan to use a Service Principal. DON'T USE QUOTATIONS!!!
# Make sure that Service Principal is data curator in Purview minimally
%env AZURE_CLIENT_ID=<<your client id without quotations>>
%env AZURE_TENANT_ID=<<your tenant id without quotations>>
%env AZURE_CLIENT_SECRET=<<your client secreat without quotations>>

# Secrets shall never be stored in plain text. Instead, use Databricks secret scope, see https://learn.microsoft.com/en-us/azure/databricks/security/secrets/secret-scopes

# COMMAND ----------

# MAGIC %sh
# MAGIC # 0.2 install purview ci
# MAGIC pip install purviewcli

# COMMAND ----------

# 0.3 load helper function
import json
def getJSON(raw_output):
  output = ''.join(raw_output)
  json_obj = json.loads(output)
  return json_obj

# COMMAND ----------

# 1. Get all files in ADLSgen2 from the collections
import purviewcli as pv
assets = !pv search query --keywords "*" --limit 1000
assets_json = getJSON(assets)
file_list = []
for value in assets_json["value"]:
    if "entityType" in value:
        if value["entityType"] == "azure_datalake_gen2_path" and value["objectType"] == "Files":
            qualifiedName_no_spaces = value["qualifiedName"].replace(" ", "%20")
            file_list.append(qualifiedName_no_spaces)

print(file_list)

# COMMAND ----------

# 2. Get all schema from files
schema_list = []
nummer = 0
for file in file_list:
    assets = !pv entity readBulkUniqueAttribute --typeName="azure_datalake_gen2_path" --qualifiedName={file}
    if assets[0] != "[INFO] No data returned in the response.":
        assets_json = getJSON(assets)
        for asset in assets_json["entities"]:
            if len(asset["relationshipAttributes"]["attachedSchema"]) > 0:
                for schema in asset["relationshipAttributes"]["attachedSchema"]:
                    term_item = {"qualifiedName": asset["attributes"]["qualifiedName"], "guid": schema["guid"]}
                    schema_list.append(term_item)

print(schema_list)

# COMMAND ----------

# 3. Get all glossary terms
# make sure SPN is data curator in Purview data plane
glossary_term_list = []

glossary = !pv glossary read
glossary_json = getJSON(glossary)
for glossary_term in glossary_json:
    for term in glossary_term["terms"]:
        term_item = {"qualifiedName": glossary_term["qualifiedName"], "displayText": term["displayText"], "termGuid": term["termGuid"]}
        glossary_term_list.append(term_item)

print(glossary_term_list)

# COMMAND ----------

# 4. Assign glossary_terms to columns in schema
for glossary_term in glossary_term_list:
    payload = []
    for schema in schema_list:

        schema_columns = !pv entity read --guid {schema["guid"]}
        schema_columns_json = getJSON(schema_columns)
        for column in schema_columns_json["entity"]["relationshipAttributes"]["columns"]:
            if glossary_term["displayText"].replace(" ", "").lower() == column["displayText"].lower():
                itemGuid = {"guid": column["guid"]}
                payload.append(itemGuid)
                print(glossary_term["displayText"] + " matched to " + column["displayText"] + " in " + schema_columns_json["entity"]["attributes"]["qualifiedName"])
    if len(payload) > 0:
        with open("payload.json", "w") as outfile:
            json.dump(payload, outfile, indent=4, sort_keys=False)

        !pv glossary createTermsAssignedEntities --termGuid {glossary_term["termGuid"]} --payloadFile "payload.json"

# COMMAND ----------
