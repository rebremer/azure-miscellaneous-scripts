from azure.identity import ClientSecretCredential 
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.datafactory import DataFactoryManagementClient
from azure.mgmt.datafactory.models import *
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# https://learn.microsoft.com/en-us/azure/data-factory/quickstart-create-data-factory-python

subscription_id = '<<your subscription>>'
rg_name = '<<your resource group>>'
df_name = '<<your adf instance>>'
credentials = ClientSecretCredential(client_id='<<your client>>', client_secret='<<your client secret>>, tenant_id='<<your tenant id>>') 
driver_name = "{<<your driver location on SHIR}"
adf_client = DataFactoryManagementClient(credentials, subscription_id)


def kv_constr_oracle_to_odbc (ls):

    # Example Oracle string
    # Host=172.201.51.245;Port=1521;Sid=oratest1;User Id=testuser;Password=MyPassword

    # Example ODBC string
    # Driver={Oracle in instantclient_21_11};Dbq=172.201.51.245:1521/ORATEST1;Uid=testuser;Pwd=MyPassword;

    ls_akv_reference = ls.properties.connection_string["store"]["referenceName"]
    ls_akv_secret_name = ls.properties.connection_string["secretName"]
    ls_akv = adf_client.linked_services.get(rg_name, factory_name=df_name, linked_service_name=ls_akv_reference)
        
    akv_client = SecretClient(vault_url=ls_akv.properties.base_url, credential=credentials)
    oracle_conn_string = akv_client.get_secret(ls_akv_secret_name).value            
    oracle_conn_list = _semicolumn_kev_value_to_list(oracle_conn_string)
    odbc_conn_list = _conn_orace_to_odbc (oracle_conn_list)
    odbc_conn_string = _list_to_semicolumn_kev_value(odbc_conn_list)
    akv_client.set_secret(ls_akv_secret_name + "ODBC2", odbc_conn_string)


def ls_oracle_to_odbc (ls):

    new_ls_conn = dict()
    new_ls_conn["connection_string"] = ls.properties.connection_string
    new_ls_conn["connection_string"]["secretName"] = ls.properties.connection_string["secretName"]  + "ODBC2"

    new_ls_odbc = LinkedServiceResource(properties=OdbcLinkedService( \
            connection_string = new_ls_conn["connection_string"], \
            additional_properties =  ls.additional_properties, \
            connect_via = ls.properties.connect_via, \
            description = ls.properties.description, \
            parameters = ls.properties.parameters, \
            annotations = ls.properties.annotations, \
            authentication_type = "anonymous") 
        ) 
    adf_client.linked_services.create_or_update(rg_name, df_name, ls.name + "ODBC", new_ls_odbc)


def ds_oracle_to_odbc (ds):

    new_ds_lsref = LinkedServiceReference( \
            type = "LinkedServiceReference", \
            reference_name  = ds.properties.linked_service_name.reference_name + "ODBC", \
            parameters = ds.properties.linked_service_name.parameters
        )
   
    new_ds_odbc = DatasetResource(properties=OdbcTableDataset( \
            linked_service_name = new_ds_lsref, \
            additional_properties =  ds.additional_properties, \
            description = ds.properties.description, \
            structure = ds.properties.structure, \
            schema = ds.properties.schema, \
            parameters = ds.properties.parameters, \
            annotations = ds.properties.annotations, \
            folder = ds.properties.folder, \
            table_name = ds.properties.table_name) 
        )
    
    adf_client.datasets.create_or_update(rg_name, df_name, ds.name + "ODBC", new_ds_odbc)


def pl_oracle_to_odbc (pl):

    for copy_activity in pl.activities:

        if copy_activity.source.type == "OracleSource":
            new_ref_name = copy_activity.inputs[0].reference_name + "ODBC"
            new_ds_input_ref = DatasetReference(type="DatasetReference", reference_name=new_ref_name)
            #
            copy_activity.inputs[0] = new_ds_input_ref
            copy_activity.source = _sourcesink_orace_to_odbc(copy_activity, "source")

    
        if copy_activity.sink.type == "OracleSink":
            new_ref_name = activity.outputs[0].reference_name + "ODBC"
            new_ds_output_ref = DatasetReference(type="DatasetReference", reference_name=activity.outputs[0].reference_name + "ODBC")
            #
            copy_activity.outputs[0] = new_ds_output_ref
            copy_activity.source = _sourcesink_orace_to_odbc(copy_activity, "sink")

    adf_client.pipelines.create_or_update(rg_name, df_name, pl.name + "ODBC", pl)


def _semicolumn_kev_value_to_list (conn_str):

    res = []
    for sub in conn_str.split(';'):
        if '=' in sub:
            res.append(map(str.strip, sub.split('=', 1)))
    res = dict(res)
    return res


def _conn_orace_to_odbc (oracle_conn_list):

    odbc_conn_list = dict()
    odbc_conn_list["Driver"] = driver_name
    odbc_conn_list["Dbq"] = oracle_conn_list["Host"] + ":" + oracle_conn_list["Port"] + "/" + oracle_conn_list["Sid"] 
    odbc_conn_list["Uid"] = oracle_conn_list["User Id"]
    odbc_conn_list["Pwd"] = oracle_conn_list["Password"]

    return odbc_conn_list


def _list_to_semicolumn_kev_value (conn_list):

    res = ""
    for sub in conn_list:
        res += sub + "=" + conn_list[sub] + ";"
    return res


def _sourcesink_orace_to_odbc(copy_activity, type):

    if type == "source":
        new_sourcesink = OdbcSource()
    else:
        new_sourcesink = OdbcSink()
    new_sourcesink.additional_columns = copy_activity.source.additional_columns
    new_sourcesink.additional_properties = copy_activity.source.additional_properties
    new_sourcesink.disable_metrics_collection = copy_activity.source.disable_metrics_collection
    new_sourcesink.max_concurrent_connections = copy_activity.source.max_concurrent_connections
    new_sourcesink.query = copy_activity.source.oracle_reader_query
    new_sourcesink.query_timeout = copy_activity.source.query_timeout
    new_sourcesink.source_retry_count = copy_activity.source.source_retry_count
    new_sourcesink.source_retry_wait = copy_activity.source.source_retry_wait
    
    return new_sourcesink


if __name__ == "__main__":

    # Step 1: convert Oracle linked service to ODBC linked services including key vault linked services
    df = adf_client.factories.get(rg_name, df_name)
    ls_list = adf_client.linked_services.list_by_factory(rg_name, factory_name=df_name)
    for ls in ls_list:
        if ls.properties.type == "Oracle":
            kv_constr_oracle_to_odbc (ls)
            ls_oracle_to_odbc(ls)

    # Step 2: convert Oracle datasets to ODBC datasets
    ds_list = adf_client.datasets.list_by_factory(rg_name, factory_name=df_name)
    for ds in ds_list:
        if ds.properties.type == "OracleTable":
            ds_oracle_to_odbc(ds)

    # Step 3: convert source/sink Oracle in copy activities to source/sink ODBC in copy activities
    pl_list = adf_client.pipelines.list_by_factory(rg_name, factory_name=df_name)
    for pl in pl_list:
        for activity in pl.activities:
            if activity.source.type == "OracleSource" or activity.sink.type == "OracleSink":
                pl_oracle_to_odbc(pl)
                break
