from azure.storage.filedatalake import DataLakeServiceClient
from azure.identity import ClientSecretCredential
import json

# Replace with your service principal details and storage account name
tenant_id = "<<your tenant id>>"
client_id = "<<your client id>>"
client_secret = "<<your secret>>"
account_name = "<<your storage account name>>"
container_name = "<<your container to be copied>>"
from azure.storage.filedatalake import DataLakeServiceClient
from azure.identity import ClientSecretCredential
import json

# Create a ClientSecretCredential
credential = ClientSecretCredential(
    tenant_id=tenant_id,
    client_id=client_id,
    client_secret=client_secret
)

# Create a DataLakeServiceClient
service_client = DataLakeServiceClient(
    account_url=f"https://{account_name}.dfs.core.windows.net",
    credential=credential
)

# Get a FileSystemClient to interact with the container
file_system_client = service_client.get_file_system_client(file_system=container_name)

def get_folder_size(file_system_client, folder_name):
    total_size = 0
    paths = file_system_client.get_paths(path=folder_name, recursive=True)
    for path in paths:
        if not path.is_directory:
            total_size += path.content_length
    return total_size

def is_parent_path_in_list(path, path_list):
    # Split the path into components
    components = path.split('/')
    
    # Generate all possible parent paths
    parent_paths = ['/'.join(components[:i]) for i in range(1, len(components))]
    
    # Check if any parent path is in the list
    for parent_path in parent_paths:
        if parent_path in path_list:
            return True
    return False

# List all directories and calculate their sizes
folders = file_system_client.get_paths()
folder_recursive_copy = []

for folder in folders:
    #print(str(folder.name))
    if folder.is_directory and not is_parent_path_in_list(folder.name, folder_recursive_copy):
        folder_size = get_folder_size(file_system_client, folder.name)
        if folder_size < 5000000000: # if folder size is less than 5GB, then data can be copied recurcively, otherwise nested folders in separate copies
            print(str(folder.name))
            folder_recursive_copy.append(folder.name)

print(json.dumps(folder_recursive_copy))

print("All folder sizes calculated successfully.")
