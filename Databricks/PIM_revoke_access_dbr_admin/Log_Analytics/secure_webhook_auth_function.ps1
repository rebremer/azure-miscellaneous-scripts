# https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/action-groups#secure-webhook

Connect-AzureAD -TenantId "<<your tenant id>>"

# Define your Azure AD application's ObjectId.
$myAzureADApplicationObjectId = "<<object ID of Azure AD app reg that is used to protect your tenant>>"

# Define the action group Azure AD AppId.
$actionGroupsAppId = "461e8683-5575-4561-ac7f-899cc907d62a"

# Define the name of the new role that gets added to your Azure AD application.
$actionGroupRoleName = "ActionGroupsSecureWebhook"

$appRole = New-Object Microsoft.Open.AzureAD.Model.AppRole
$appRole.AllowedMemberTypes = New-Object System.Collections.Generic.List[string]
$appRole.AllowedMemberTypes.Add("Application");
$appRole.DisplayName = "ActionGroupsSecureWebhook"
$appRole.Id = New-Guid
$appRole.IsEnabled = $true
$appRole.Description = "This is a role for Action Group to join"
$appRole.Value = "ActionGroupsSecureWebhook"

# Get your Azure AD application, its roles, and its service principal.
$myApp = Get-AzureADApplication -ObjectId $myAzureADApplicationObjectId
$myAppRoles = $myApp.AppRoles
$actionGroupsSP = Get-AzureADServicePrincipal -Filter ("appId eq '" + $actionGroupsAppId + "'")

Write-Host "App Roles before addition of new role.."
Write-Host $myAppRoles

# Add the new role to the Azure AD application.
$newRole = $appRole
$myAppRoles.Add($newRole)
Set-AzureADApplication -ObjectId $myApp.ObjectId -AppRoles $myAppRoles

# $actionGroupsSP = New-AzureADServicePrincipal -AppId $actionGroupsAppId

New-AzureADServiceAppRoleAssignment -Id $myApp.AppRoles[0].Id -ResourceId $myServicePrincipal.ObjectId -ObjectId $actionGroupsSP.ObjectId -PrincipalId $actionGroupsSP.ObjectId

Write-Host "My Azure AD Application (ObjectId): " + $myApp.ObjectId
Write-Host "My Azure AD Application's Roles"
Write-Host $myApp.AppRoles