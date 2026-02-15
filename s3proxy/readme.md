# S3Proxy: Script using Azure Storage with the S3 API

1. Download S3Proxy from https://github.com/gaul/s3proxy. Make sure that Java installed and the JAVA_HOME variable is set. For instance Microsoft OpenJDK can be installed via winget install Microsoft.OpenJDK.25

2. Configure storage account in s3proxy.conf using Storage SDK following explanation in this link: https://github-wiki-see.page/m/gaul/s3proxy/wiki/Storage-backend-examples

Make sure that environment variables are set and that SPN/MI used has ```Storage Blob Data Contributor``` access on the Storage account. Environment varialbes for SPN need to set as follows:

```
$AZURE_TENANT_ID=<<Your Azure Tenant>>
$AZURE_CLIENT_ID=<<Your app Id>>
$AZURE_CLIENT_SECRET=<<Your secret>>
```

3. Run S3 proxy locally via this via this command: ```java -jar s3proxy --properties s3proxy.conf```

4. Create bucket using the S3Proxy that results in a Container on Azure Storage

```
Invoke-WebRequest `
  -Method PUT `
  -Uri http://localhost:8080/testbucket

```

5. Add file to bucket

```
Invoke-WebRequest `
  -Method PUT `
  -InFile .\hello.txt `
  -Uri http://localhost:8080/testbucket/hello.txt `
  -ContentType "application/octet-stream"
```
