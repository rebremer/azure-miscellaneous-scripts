CREATE TABLE dbo.Employee (
    EmployeeID INT NOT NULL,
    Name        VARCHAR(50) NOT NULL,
    Country     VARCHAR(2)  NOT NULL,
    StartYear   INT         NOT NULL
);

INSERT INTO dbo.Employee (EmployeeID, Name, Country, StartYear)
VALUES
    (1, 'Rene', 'US', 2017),
    (2, 'Marlous',  'IN', 2008),
    (3, 'Thom',   'GB', 2011),
    (4, 'Krijn',  'US', 2013),
    (5, 'Stef',   'US', 2015);

CREATE TABLE dbo.public_holiday_country
(
    Country     VARCHAR(2)   NOT NULL,
    [Date]      DATE         NOT NULL,
    [Name]      VARCHAR(100) NOT NULL
);

INSERT INTO dbo.public_holiday_country (Country, [Date], [Name])
VALUES
-- United States (US)
('US', '2024-01-01', 'New Year''s Day'),
('US', '2024-01-15', 'Martin Luther King Jr. Day'),
('US', '2024-07-04', 'Independence Day'),
('US', '2024-11-28', 'Thanksgiving Day'),
('US', '2024-12-25', 'Christmas Day'),

-- India (IN)
('IN', '2024-01-26', 'Republic Day'),
('IN', '2024-03-25', 'Holi'),
('IN', '2024-08-15', 'Independence Day'),
('IN', '2024-10-02', 'Gandhi Jayanti'),
('IN', '2024-11-01', 'Diwali'),

-- United Kingdom (GB)
('GB', '2024-01-01', 'New Year''s Day'),
('GB', '2024-03-29', 'Good Friday'),
('GB', '2024-04-01', 'Easter Monday'),
('GB', '2024-05-06', 'Early May Bank Holiday'),
('GB', '2024-12-25', 'Christmas Day');


CREATE OR ALTER VIEW dbo.vw_Employee_Holidays
AS
SELECT
    e.EmployeeID,
    e.Name,
    e.Country,
    e.StartYear,
    h.[Date]        AS HolidayDate,
    h.[Name]        AS HolidayName
FROM dbo.Employee AS e
LEFT JOIN dbo.public_holiday_country AS h
    ON e.Country = h.Country;
GO
