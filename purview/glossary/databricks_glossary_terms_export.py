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

# 3. Update the path to your local entities_to_term.csv file path
PATH_TO_CSV ="/dbfs/testpurview.csv" # quotations

# 4. Term to which glossary items need to be linked
TERM_FORMAL_NAME = "testrb4" # quoations

# COMMAND ----------

# MAGIC %sh
# MAGIC pip install purviewcli

# COMMAND ----------

import json
def getJSON(raw_output):
  output = ''.join(raw_output)
  json_obj = json.loads(output)
  return json_obj

# COMMAND ----------

import purviewcli as pv

#assets = !pv entity read --guid <<GUID of SQL Server with contains child db, tables, fields) or Storage account>>
assets = !pv entity read --guid "5932d77a-535e-4c71-b574-da17e772606e"
#print(assets)
assets_json = getJSON(assets)

# COMMAND ----------

rows = "guid,qualifiedName,termFormalName\n"

for asset in assets_json['referredEntities']:
  guid = asset
  #print(guid)
  qualifiedName = assets_json['referredEntities'][guid]["attributes"]["qualifiedName"]
  rows += guid + "," + qualifiedName + "," + TERM_FORMAL_NAME + "\n"
  
PATH_TO_CSV ="/dbfs/testpurview.csv"
with open(PATH_TO_CSV, "w") as text_file:
    text_file.write(rows)

# COMMAND ----------

# MAGIC %sh
# MAGIC cat /dbfs/testpurview.csv

# COMMAND ----------

# 1. Convert mapping from CSV to Dictionary
import csv
terms = {}
with open(PATH_TO_CSV) as fp:
    reader = csv.reader(fp, delimiter=",", quotechar='"')
    next(reader, None) # skip headers
    for row in reader:
        guid, qualifiedName, termFormalName = row[0],row[1],row[2]
        if termFormalName in terms:
            terms[termFormalName].append(guid)
        else:
            terms[termFormalName] = []
            terms[termFormalName].append(guid)

# COMMAND ----------

# 2. Get Glossary
# make sure SPN is data curator in Purview data plane
import purviewcli as pv

glossary = !pv glossary read
#print (glossary)
glossary = getJSON(glossary)

print(glossary[0]['terms'])

# COMMAND ----------

# 3. Get Term GUID function
def getTermGuid(termFormalName, glossary):
    termGuid = None
    for term in glossary[0]['terms']:
        if term['displayText'] == termFormalName:
            termGuid = term['termGuid']
    print(str(termGuid))
    return termGuid

# COMMAND ----------

# 4. Assign terms to entities
for term in terms:
    print(term)
    termGuid = getTermGuid(term, glossary)
    numberOfEntities = len(terms[term])
    if numberOfEntities > 0:
        payload = []
        for entity in terms[term]:
            item = {"guid": entity}
            print(str(item))
            payload.append(item)
        with open("payload.json", "w") as outfile:
            json.dump(payload, outfile, indent=4, sort_keys=False)
        !pv glossary createTermsAssignedEntities --termGuid {termGuid} --payloadFile "payload.json"

# COMMAND ----------
