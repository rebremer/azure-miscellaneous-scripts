/****** Object:  Table [dbo].[movies]    Script Date: 10/10/2022 8:51:22 AM ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE TABLE [dbo].[movies](
	[movie] [nvarchar](max) NULL,
	[title] [nvarchar](max) NULL,
	[genres] [nvarchar](max) NULL,
	[year] [nvarchar](max) NULL,
	[Rating] [nvarchar](max) NULL,
	[Rotton Tomato] [nvarchar](max) NULL
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
