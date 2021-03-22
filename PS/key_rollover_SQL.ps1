# PowerShell script that does a key rollover in Azure SQL
# - Required cmdlets are installed
# - Authentication using Azure AD (when using Azure DevOps is used, Azure context is already set)
# - Generate new password for Azure SQL
# - Write secret to key vault

# https://blog.kloud.com.au/2016/04/12/creating-accounts-on-azure-sql-database-through-powershell-automation/
# 0. params
# 0.1 Azure
$tenant_id = "<<your tenant id>>"
$subscription_id = "<<your subscription id>>"
$akv_name = "<<your key vault name>>"
$akv_secretname_sqlpbirs_user = "<<your secret name in key vault containing sqldb pbirs user name>>"
$akv_secretname_sqlpbirs_password = "<<your secret name in key vault containing sqldb pbirs user password>>"
$sql_server_name = "<<your sql server name>>.database.windows.net"
$sql_db_name = "<<your sql db name>>"
$rg_name = "<<your resource group name>>"
# 0.2 PBI report
$report_server_url = "<<your report server url>>" # precondition is that deployment script is run in the same domain as report server
$report_server_map = "<<your report server map to which report is deployed"
$local_map_report = "<<your local map where report is stored>>"
$report_name = "<<your report name>>"

Function GenerateStrongPassword ([Parameter(Mandatory=$true)][int]$PasswordLenght)
{
   Add-Type -AssemblyName System.Web
   $PassComplexCheck = $false
   do {
        $newPassword=[System.Web.Security.Membership]::GeneratePassword($PasswordLenght,1)
        If ( ($newPassword -cmatch "[A-Z\p{Lu}\s]") `
          -and ($newPassword -cmatch "[a-z\p{Ll}\s]") `
          -and ($newPassword -match "[\d]") `
          -and ($newPassword -match "[^\w]")
        )
        {
          $PassComplexCheck=$True
        }
      } 
      While ($PassComplexCheck -eq $false)
      
      return $newPassword
}

# https://github.com/Microsoft/ReportingServicesTools
#Install-Module -Name ReportingServicesTools
#Install-Module -Name Az.Accounts
#Install-Module -Name Az.KeyVault
#Install-Module -Name Az.Sql

Clear-AzContext -Force
Connect-AzAccount -Tenant $tenant_id -SubscriptionId $subscription_id
Set-AzContext -SubscriptionId $subscription_id
Get-AzContext

# 1a. Azure AD authentication. Domain join is required, see https://docs.microsoft.com/en-us/azure/azure-sql/database/authentication-aad-configure?tabs=azure-powershell#active-directory-integrated-authentication-1 
$connectionString = "Server=tcp:test-sqldbpowerbionprem-sql2.database.windows.net,1433; Initial Catalog=master;MultipleActiveResultSets=False;Persist Security Info=False;Encrypt=True;TrustServerCertificate=False;Authentication='Active Directory Integrated'";
# 1b. SQL authentication
#$akv_secretname_sqladmin_user = "<<your secret name in key vault containing sqldb admin user name>>"
#$akv_secretname_sqladmin_password = "<<your secret name in key vault containing sqldb admin user password>>"
#connectionString = "Server=tcp:test-sqldbpowerbionprem-sql2.database.windows.net,1433; Initial Catalog=master;MultipleActiveResultSets=False;Persist Security Info=False;Encrypt=True;TrustServerCertificate=False;User ID=$(Get-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_sqladmin_user -AsPlainText);Password=$(Get-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_sqladmin_password -AsPlainText)";
$connection = New-Object -TypeName System.Data.SqlClient.SqlConnection($connectionString)

# 2. Build query
$queryPath = "C:\Users\bremerov\Desktop\resetsqlpassword.sql"
$query = [System.IO.File]::ReadAllText($queryPath)
$command = New-Object -TypeName System.Data.SqlClient.SqlCommand($query, $connection)

# 3. Generate password
$ServerPassword = GenerateStrongPassword (10)
$secPw = ConvertTo-SecureString -String $ServerPassword -AsPlainText -Force
$password = New-Object -TypeName System.Data.SqlClient.SqlParameter("@Password", "$($ServerPassword)")

# 4. Add parameters to query
$Username = New-Object -TypeName System.Data.SqlClient.SqlParameter("@Username", "$(Get-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_sqlpbirs_user -AsPlainText)")
$command.Parameters.Add($Username)
$command.Parameters.Add($Password)

# 4. Execute query
$connection.Open()
$command.ExecuteNonQuery()
$connection.Close()

# 5. Add new password to key vault
$secret = Set-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_sqlpbirs_password -SecretValue $secPw

# 6. Write key to Report server
# establish session w/ Report Server
$session = New-RsRestSession -ReportPortalUri http://$report_server_url/Reports

# set passwords
$dataSources = Get-RsRestItemDataSource -WebSession $session -RsItem "/$($report_server_map)/$($report_name)"
$dataSources[0].DataModelDataSource.Username = Get-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_sqlpbirs_user -AsPlainText
$dataSources[0].DataModelDataSource.Secret = Get-AzKeyVaultSecret -VaultName $akv_name -Name $akv_secretname_sqlpbirs_password -AsPlainText
$dataSources[0].DataModelDataSource.AuthType = 'UsernamePassword'
Set-RsRestItemDataSource -RsItem "/$($report_server_map)/$($report_name)" -RsItemType 'PowerBIReport' -DataSources $dataSources
