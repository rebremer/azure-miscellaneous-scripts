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
$akv_secretname_sqlpbirs_user = "<<your secret name in key vault containing sqldb pbirs user name>>"
$akv_secretname_sqlpbirs_password = "<<your secret name in key vault containing sqldb pbirs user password>>"
$sql_server_name = "<<your sql server name>>.database.windows.net"
$sql_db_name = "<<your sql db name>>"
# 0.2 PBIRS report
$report_server_url = "<<your report server url>>" # precondition is that deployment script is run in the same domain as report server
$report_server_map = "<<your report server map to which report is deployed>>"
$local_map_report = "<<your local map where report is stored>>"
$report_name = "<<your report name>>"
# 0.3 Windows
# akv_secretname_windowspbirs_user and akv_secretname_windowspbirs_password are needed when reports are deployed from remote machine 
# and remote machine and PBI report server are not domain joined
$akv_secretname_windowspbirs_user = "<<your secret name in key vault containing windows pbirs user name>>"
$akv_secretname_windowspbirs_password = "<<your secret name in key vault containing windows pbirs user password>>"

# 1. Install required modules (only once)
# https://github.com/Microsoft/ReportingServicesTools
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
#Install-Module -Name ReportingServicesTools
#Install-Module -Name Az.Accounts
#Install-Module -Name Az.KeyVault

# 2. Establish connection to Azure Key Vault using Azure AD where secrets are stored
Clear-AzContext -Force
Connect-AzAccount -Tenant $tenant_id -SubscriptionId $subscription_id
Set-AzContext -SubscriptionId $subscription_id
Get-AzContext

# 3. Establish session to Report Server.
# 3.1 With PSCredential object using windows user
$windows_username = Get-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_windowspbirs_user -AsPlainText
$sec_windows_password = ConvertTo-SecureString $(Get-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_windowspbirs_password -AsPlainText)-AsPlainText -Force
$credObject = New-Object System.Management.Automation.PSCredential ($windows_username, $sec_windows_password)
$session = New-RsRestSession -ReportPortalUri http://$($report_server_url)/Reports -Credential $credObject
# 3.2 Without PSCredential object (e.g. when reports are deployed from PBI report server itself and windows user is already authenticated)
#$session = New-RsRestSession -ReportPortalUri http://$($report_server_url)/Reports -Credential $credObject

# 4. Create folder (optional, only once)
try{
  New-RsRestFolder -WebSession $session -RsFolder $report_server_map -FolderName $report_server_map -Overwrite True
}
catch
{
}

# 5. upload copy of PBIX to new folder
Write-RsRestCatalogItem -Overwrite True -WebSession $session -Path "$($local_map_report)\$($report_name).pbix" -RsFolder "/$($report_server_map)"

# 6. Reset connection string (e.g. point connection string to production server/sqldb). Notice that credential are only added in step 7
$parameters = Get-RsRestItemDataModelParameters "/$($report_server_map)/$($report_name)" -WebSession $session
$parameterdictionary = @{}
foreach ($parameter in $parameters) { $parameterdictionary.Add($parameter.Name, $parameter); }
$parameterdictionary[“server”].Value = $sql_server_name
$parameterdictionary[“database”].Value = $sql_db_name
Set-RsRestItemDataModelParameters -RsItem "/$($report_server_map)/$($report_name)" -DataModelParameters $parameters -WebSession $session

# 7. Retrieve credentials from sqlusername/password from key vault (e.g. user production sqluser/sqlpassword with sql user only having access on need to know and readonly)
$dataSources = Get-RsRestItemDataSource -WebSession $session -RsItem "/$($report_server_map)/$($report_name)"
$dataSources[0].DataModelDataSource.Username = Get-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_sqlpbirs_user -AsPlainText
$dataSources[0].DataModelDataSource.Secret = Get-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_sqlpbirs_password -AsPlainText
$dataSources[0].DataModelDataSource.AuthType = 'UsernamePassword'
Set-RsRestItemDataSource -RsItem "/$($report_server_map)/$($report_name)" -RsItemType 'PowerBIReport' -DataSources $dataSources -WebSession $session
