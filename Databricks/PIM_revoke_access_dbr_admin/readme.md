# Revoke access of Databricks Admin after PIM expired
Privileged Access Management (PIM) is used to temporarily grant access to resources. In Azure Databricks, PIM can be used make a user Contributor. After a user is made Contributor, user can log into Databricks and becomes a Databricks Admin. However, when PIM is expired and Contributor role is revoked, the user remains Admin in Databricks. This project makes sure that user is also revoked as Admin after PIM expired. This is done as follows:

- Every IAM action is logged in Activity Log. Databricks Activity Log is propagated to Log Analytics
- ```Log_analytics\detect_IAM_contributor_removed.kusto``` is used to detect the Object ID of the user from which Contributor Role was revoked
- ```Log_analytics\alert_rule.json``` runs the kusto query every 5 minutes to check whether there is a revoked user
- In case there is a revoked user, ```Log_analytics\action_group.json``` is triggered that calls a secure webhook passing the object ID of the user
- Secure webhook is Azure Function ```Azure_Function\HttpTriggerDatabricksSCIM```. The Azure Function uses the object Id in the HTTP post to check whether user still exists in Databricks using the SCIM interface and if so, deletes the user.
  - ```Log_analytics\secure_webhook_auth_function.ps1``` is used to make sure that only ActionGroupsSecureWebhook can call Azure Function after Azure AD authentitcation on Azure Function is enabled.
  - Managed Identity of Azure Function needs to be Contributor on Databricks in order to be able to authenticate to Databricsk and to be authorized to use SCIM interface

Steps to take:
1. Deploy Azure Databricks workspace, Log Analytics Workspace and Azure Functions in Python
2. Enable Managed Identity in Azure Function and grant Azure Function Contributor Role in Databricks workspace
3. Deploy code in ```Azure_Function\``` to Azure Function. Configure in databricks_api and databricks_id in environment variables of Azure Function. Copy Azure Function URL.
4. Create alert_rule and alert_group in Log analytics using code in ```Log_Analytics```. In the Action group, use the URL of the Azure Function step 3 as secure webhook.
5. Run a couple of tests in which user is added as Contributor in Databricks, log in with user in Databricks, revoke Contributor and then check if user is deleted as user in Databricsk after a couple of minutes
6. After tests are successful, enable Azure AD authentication on Azure Function. The run script ```Log_analytics\secure_webhook_auth_function.ps1``` to grant Action Group in Log Analytics access to Azure Functions. Notice that user needs the have "Azure AD Application Adminstrator" rights, see also [here](https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/action-groups#secure-webhook)
