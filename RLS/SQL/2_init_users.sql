CREATE USER [Employee_IN] FROM EXTERNAL PROVIDER -- Indian users in this group In
CREATE USER [Employee_US] FROM EXTERNAL PROVIDER -- US users in this group

ALTER ROLE db_datareader ADD MEMBER [Employee_IN];
ALTER ROLE db_datareader ADD MEMBER [Employee_US];