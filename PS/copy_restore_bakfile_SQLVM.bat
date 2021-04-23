REM 0 bat script that fetches .bak file from Storage acocunt using SQLVM MI and then restores it to database. Todo: substitute parameters
REM
REM 1. set parames
set vm_client_id="<<client ID of SQLVM MI>>"
set source="https://blogsnapshotautstor.blob.core.windows.net/feyenoord/AdventureWorksLT2019.bak"
set dest="C:\Program Files\Microsoft SQL Server\MSSQL15.MSSQLSERVER\MSSQL\Backup\AdventureWorksLT2019.bak"
set servername="blog-sql-onprem"
set dbname="testrbxyz"
REM
REM 2. Fetch file from blob storage
azcopy login --identity --identity-client-id %vm_client_id%
azcopy copy %source% %dest% --recursive
REM
REM 3. Restore databae
REM Permissions needed: https://stackoverflow.com/questions/3960257/cannot-open-backup-device-operating-system-error-5
SET restorecmd=RESTORE DATABASE %dbname% FROM DISK='C:\Users\bremerov\Desktop\AdventureWorksLT2019.bak'
sqlcmd -E -S %servername% -Q "RESTORE DATABASE testrb FROM DISK='C:\Users\bremerov\Desktop\AdventureWorksLT2019.bak' WITH FILE = 1, MOVE N'AdventureWorksLT2012_Data' TO N'C:\Program Files\Microsoft SQL Server\MSSQL15.MSSQLSERVER\MSSQL\Backup\AdventureWorksLT2012_Data.mdf', MOVE N'AdventureWorksLT2012_Log' TO N'C:\Program Files\Microsoft SQL Server\MSSQL15.MSSQLSERVER\MSSQL\Backup\AdventureWorksLT2012_Log.ldf'"
