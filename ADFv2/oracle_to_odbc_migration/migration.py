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


class KeyVaultMigration:


    def oracle_to_odbc (ls):
        # Example Oracle string
        # Host=172.201.51.245;Port=1521;Sid=oratest1;User Id=testuser;Password=MyPassword
        #
        # Example ODBC string
        # Driver={Oracle in instantclient_21_11};Dbq=172.201.51.245:1521/ORATEST1;Uid=testuser;Pwd=MyPassword;
        ls_akv_reference = ls.properties.connection_string["store"]["referenceName"]
        ls_akv_secret_name = ls.properties.connection_string["secretName"]
        ls_akv = adf_client.linked_services.get(rg_name, factory_name=df_name, linked_service_name=ls_akv_reference)
        
        akv_client = SecretClient(vault_url=ls_akv.properties.base_url, credential=credentials)
        oracle_conn_string = akv_client.get_secret(ls_akv_secret_name).value            
        oracle_conn_list = KeyVaultMigration._semicolumn_kev_value_to_list(oracle_conn_string)
        odbc_conn_list = KeyVaultMigration._conn_orace_to_odbc (oracle_conn_list)
        odbc_conn_string = KeyVaultMigration._list_to_semicolumn_kev_value(odbc_conn_list)

        akv_client.set_secret(ls_akv_secret_name + "ODBC2", odbc_conn_string)


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


class LinkedServiceMigration:


    def oracle_to_odbc (ls):
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


class DatasetMigration:


    def oracle_to_odbc (ds):
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


class PipelineMigration:


    def has_oracle_activities (pl):
        pl_has_oracle_activities = False
        for activity in pl.activities:
            if PipelineMigration.ActivityMigration.is_oracle_activity(activity):
                pl_has_oracle_activities = True
                break
        
        return pl_has_oracle_activities


    def oracle_to_odbc (pl):
        for activity in pl.activities:
            if PipelineMigration.ActivityMigration.is_oracle_activity (activity):
                PipelineMigration.ActivityMigration.migrate_oracle_to_odbc(activity)

        adf_client.pipelines.create_or_update(rg_name, df_name, pl.name + "ODBC", pl)


    class ActivityMigration:


        def is_oracle_activity(activity):
            is_oracle_activity = False
            if activity.type == "Copy":
                if activity.source.type == "OracleSource" or \
                    activity.sink.type == "OracleSink":
                    is_oracle_activity = True
            elif activity.type == "Script":
                ls = adf_client.linked_services.get(rg_name, df_name, activity.linked_service_name.reference_name)
                if ls.properties.type == "Oracle":
                    is_oracle_activity = True
            elif activity.type == "Lookup":
                ds = adf_client.datasets.get(rg_name, df_name, activity.dataset.reference_name)
                if ds.properties.type == "OracleTable":
                    is_oracle_activity = True

            return is_oracle_activity


        def migrate_oracle_to_odbc(activity):
            if activity.type == "Copy":
                   PipelineMigration.ActivityMigration._copy_oracle_to_odbc(activity)
            elif activity.type == "Script":
                PipelineMigration.ActivityMigration._script_oracle_to_odbc(activity)
            elif activity.type == "Lookup":
                PipelineMigration.ActivityMigration._lookup_oracle_to_odbc(activity)


        def _copy_oracle_to_odbc(activity):
            if activity.source.type == "OracleSource":
                new_ref_name = activity.inputs[0].reference_name + "ODBC"
                activity.inputs[0] = DatasetReference(type="DatasetReference", reference_name=new_ref_name)
                activity.source = PipelineMigration.ActivityMigration._source_oracle_to_odbc(activity)
            if activity.sink.type == "OracleSink":
                new_ref_name = activity.outputs[0].reference_name + "ODBC"
                activity.outputs[0] = DatasetReference(type="DatasetReference", reference_name=new_ref_name)
                activity.source = PipelineMigration.ActivityMigration._sink_oracle_to_odbc(activity)


        def _script_oracle_to_odbc(activity):
            new_script_lsref = LinkedServiceReference( \
                type = "LinkedServiceReference", \
                reference_name  = activity.linked_service_name.reference_name + "ODBC", \
                parameters = activity.linked_service_name.parameters
            )
            
            raise ScriptException("Script migration from oracle to odbc is not supported")


        def _lookup_oracle_to_odbc(activity):
            new_ref_name = activity.dataset.reference_name + "ODBC"
            #
            activity.dataset = DatasetReference(type="DatasetReference", reference_name=new_ref_name)
            activity.source = PipelineMigration.ActivityMigration._source_oracle_to_odbc(activity)


        def _source_oracle_to_odbc(activity):
            new_source = OdbcSource()
            new_source.query = activity.source.oracle_reader_query
            new_source = PipelineMigration.ActivityMigration._generic_source_sink_orace_to_odbc(activity, new_source)
            
            return new_source


        def _sink_orace_to_odbc(activity):
            new_sink = OdbcSink()
            new_sink = PipelineMigration.ActivityMigration._generic_source_sink_orace_to_odbc(activity, new_sink)
            
            return new_sink


        def _generic_source_sink_orace_to_odbc(activity, sourcesink):
            sourcesink.additional_columns = activity.source.additional_columns
            sourcesink.additional_properties = activity.source.additional_properties
            sourcesink.disable_metrics_collection = activity.source.disable_metrics_collection
            sourcesink.max_concurrent_connections = activity.source.max_concurrent_connections
            sourcesink.query_timeout = activity.source.query_timeout
            sourcesink.source_retry_count = activity.source.source_retry_count
            sourcesink.source_retry_wait = activity.source.source_retry_wait
    
            return sourcesink


class ScriptException(Exception):
    pass


if __name__ == "__main__":
    # Step 1: convert Oracle linked service to ODBC linked services including key vault linked services
    df = adf_client.factories.get(rg_name, df_name)
    ls_oracle = False
    ls_list = adf_client.linked_services.list_by_factory(rg_name, factory_name=df_name)
    for ls in ls_list:
        if ls.properties.type == "Oracle":
            ls_oracle = True
            KeyVaultMigration.oracle_to_odbc (ls)
            LinkedServiceMigration.oracle_to_odbc(ls)
    if not ls_oracle:
        print ("Oracle driver not used, nothing to migrate")
        exit(0)

    # Step 2: convert Oracle datasets to ODBC datasets
    ds_list = adf_client.datasets.list_by_factory(rg_name, factory_name=df_name)
    for ds in ds_list:
        if ds.properties.type == "OracleTable":
            DatasetMigration.oracle_to_odbc(ds)

    # Step 3: convert source/sink Oracle in copy activities to source/sink ODBC in copy activities
    pl_list = adf_client.pipelines.list_by_factory(rg_name, factory_name=df_name)
    for pl in pl_list:
        if PipelineMigration.has_oracle_activities (pl): 
            PipelineMigration.oracle_to_odbc(pl)
