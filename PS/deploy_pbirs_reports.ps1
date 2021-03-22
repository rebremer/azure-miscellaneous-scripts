# PowerShell script that deploys PBI report to report server. In this, the following is done:
# - Required cmdlets are installed
# - Authentication using Azure AD (when using Azure DevOps is used, Azure context is already set)
# - Retrieve secret from key vault (make sure SQL passwords is added to key vault and Azure DevOps SPN has rights to fetch secret
# - Deploy PBI report to report server
# - Reset sql server name and database name using parameters
# - Reset username and password (password coming from key vaul)
# See also https://docs.microsoft.com/en-us/power-bi/report-server/connect-data-source-apis

# 0. params
# 0.1 Azure
$tenant_id = "<<your tenant id>>"
$subscription_id = "<<your subscription id>>"
$akv_name = "<<your key vault name>>"
$akv_secretname_sqluser = "<<your secret name in key vault containing sqldb user name>>"
$akv_secretname_sqlpassword = "<<your secret name in key vault containing sqldb user password>>"
$sql_server_name = "<<your sql server name>>.database.windows.net"
$sql_db_name = "<<your sql db name>>"
# 0.2 PBIRS report
$report_server_url = "<<your report server url>>" # precondition is that deployment script is run in the same domain as report server
$report_server_map = "<<your report server map to which report is deployed"
$local_map_report = "<<your local map where report is stored>>"
$report_name = "<<your report name>>"

# https://github.com/Microsoft/ReportingServicesTools
#Install-Module -Name ReportingServicesTools
#Install-Module -Name Az.Accounts
#Install-Module -Name Az.KeyVault

#Clear-AzContext -Force
#Connect-AzAccount -Tenant $tenant_id -SubscriptionId $subscription_id
#Set-AzContext -SubscriptionId $subscription_id
#Get-AzContext

# establish session w/ Report Server
$session = New-RsRestSession -ReportPortalUri http://$report_server_url/Reports

# create folder (optional)
try{
  New-RsRestFolder -WebSession $session -RsFolder $report_server_map -FolderName $report_server_map -Overwrite True
}
catch
{
}

# upload copy of PBIX to new folder
Write-RsRestCatalogItem -Overwrite True -WebSession $session -Path "$($local_map_report)\$($report_name).pbix" -RsFolder "/$($report_server_map)"

# set parameters
# "/DeployPS/reportsqlparamsPS"
$parameters = Get-RsRestItemDataModelParameters "/$($report_server_map)/$($report_name)"
$parameterdictionary = @{}
foreach ($parameter in $parameters) { $parameterdictionary.Add($parameter.Name, $parameter); }
$parameterdictionary[“server”].Value = $sql_server_name
$parameterdictionary[“database”].Value = $sql_db_name
Set-RsRestItemDataModelParameters -RsItem "/$($report_server_map)/$($report_name)" -DataModelParameters $parameters

# set passwords
$dataSources = Get-RsRestItemDataSource -WebSession $session -RsItem "/$($report_server_map)/$($report_name)"
$dataSources[0].DataModelDataSource.Username = Get-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_sqluser -AsPlainText
$dataSources[0].DataModelDataSource.Secret = Get-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_sqlpassword -AsPlainText
$dataSources[0].DataModelDataSource.AuthType = 'UsernamePassword'
Set-RsRestItemDataSource -RsItem "/$($report_server_map)/$($report_name)" -RsItemType 'PowerBIReport' -DataSources $dataSources
