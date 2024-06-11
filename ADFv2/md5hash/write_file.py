from azure.storage.blob import BlobServiceClient, BlobClient
from azure.identity import DefaultAzureCredential
import pandas as pd
import os

# Assuming df is your Spark DataFrame
data = [(1, 'foo'), (2, 'bar')]

# Create a DataFrame from the list of tuples
pdf = pd.DataFrame(data, columns=['id', 'value'])

# Write the Pandas DataFrame to a CSV file
csv_file = 'data.csv'
pdf.to_csv(csv_file, index=False)

def main():
    # Create a service client using the default Azure credential
    account_url = "https://<<your storage account>>.blob.core.windows.net"
    credential = DefaultAzureCredential()

    service_client = BlobServiceClient(account_url, credential=credential)

    # Create a blob client for the CSV file
    blob_client = service_client.get_blob_client("md5hash", csv_file)

    # Upload the CSV file to Azure Blob Storage
    with open(csv_file, 'rb') as f:
        blob_client.upload_blob(f, overwrite=True)

    # Delete the local CSV file
    os.remove(csv_file)

if __name__ == "__main__":
    main()
