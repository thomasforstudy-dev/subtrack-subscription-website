/* ==========================================================================
   SubTrack — database schema (SQL Server / T-SQL)

   How to run:
     1. Open SSMS and connect to  localhost\SQLEXPRESS
     2. File > Open > File... and pick this file
     3. Press Execute (F5)

   Safe to run again: it only creates what doesn't exist yet, and refreshes
   the views. It never deletes your data.

   Keep in sync with app/models.py.
   ========================================================================== */

IF DB_ID(N'SubTrack') IS NULL
    CREATE DATABASE SubTrack;
GO

USE SubTrack;
GO

/* ---------- users: one row per account --------------------------------- */
IF OBJECT_ID(N'dbo.users', N'U') IS NULL
CREATE TABLE dbo.users (
    id             INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_users PRIMARY KEY,
    email          NVARCHAR(255)     NOT NULL CONSTRAINT UQ_users_email UNIQUE,
    password_hash  NVARCHAR(255)     NOT NULL,   -- never the real password
    is_admin       BIT               NOT NULL CONSTRAINT DF_users_is_admin DEFAULT (0),
    created_at     DATETIME2         NOT NULL CONSTRAINT DF_users_created_at DEFAULT (SYSUTCDATETIME()),
    last_login_at  DATETIME2         NULL
);
GO

/* ---------- subscriptions: what each user pays for --------------------- */
IF OBJECT_ID(N'dbo.subscriptions', N'U') IS NULL
CREATE TABLE dbo.subscriptions (
    id               INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_subscriptions PRIMARY KEY,
    user_id          INT               NOT NULL
                     CONSTRAINT FK_subscriptions_users REFERENCES dbo.users (id) ON DELETE CASCADE,
    name             NVARCHAR(120)     NOT NULL,
    amount           DECIMAL(10, 2)    NOT NULL CONSTRAINT DF_subscriptions_amount DEFAULT (0)
                     CONSTRAINT CK_subscriptions_amount CHECK (amount >= 0),
    currency         NVARCHAR(8)       NOT NULL CONSTRAINT DF_subscriptions_currency DEFAULT (N'USD'),
    [cycle]          NVARCHAR(20)      NOT NULL CONSTRAINT DF_subscriptions_cycle DEFAULT (N'monthly')
                     CONSTRAINT CK_subscriptions_cycle CHECK ([cycle] IN (N'weekly', N'monthly', N'yearly')),
    next_renewal_at  DATE              NOT NULL,
    remind_days      INT               NOT NULL CONSTRAINT DF_subscriptions_remind_days DEFAULT (7)
                     CONSTRAINT CK_subscriptions_remind_days CHECK (remind_days BETWEEN 0 AND 365),
    status           NVARCHAR(20)      NOT NULL CONSTRAINT DF_subscriptions_status DEFAULT (N'active')
                     CONSTRAINT CK_subscriptions_status CHECK (status IN (N'active', N'archived')),
    notes            NVARCHAR(MAX)     NOT NULL CONSTRAINT DF_subscriptions_notes DEFAULT (N''),
    created_at       DATETIME2         NOT NULL CONSTRAINT DF_subscriptions_created_at DEFAULT (SYSUTCDATETIME())
);
GO

-- Speeds up "this user's subscriptions, soonest renewal first".
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_subscriptions_user_renewal')
    CREATE INDEX IX_subscriptions_user_renewal
        ON dbo.subscriptions (user_id, status, next_renewal_at);
GO

/* ---------- reminder_logs: one row per reminder sent ------------------- */
IF OBJECT_ID(N'dbo.reminder_logs', N'U') IS NULL
CREATE TABLE dbo.reminder_logs (
    id               INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_reminder_logs PRIMARY KEY,
    subscription_id  INT               NOT NULL
                     CONSTRAINT FK_reminder_logs_subscriptions REFERENCES dbo.subscriptions (id) ON DELETE CASCADE,
    renewal_date     DATE              NOT NULL,   -- which renewal this reminder was for
    sent_at          DATETIME2         NOT NULL CONSTRAINT DF_reminder_logs_sent_at DEFAULT (SYSUTCDATETIME()),
    channel          NVARCHAR(20)      NOT NULL CONSTRAINT DF_reminder_logs_channel DEFAULT (N'email'),
    result           NVARCHAR(40)      NOT NULL CONSTRAINT DF_reminder_logs_result DEFAULT (N'pending'),
    -- The same renewal can never be reminded twice on the same channel.
    CONSTRAINT UQ_reminder_once UNIQUE (subscription_id, renewal_date, channel)
);
GO

/* ---------- links: websites the user pinned ---------------------------- */
IF OBJECT_ID(N'dbo.links', N'U') IS NULL
CREATE TABLE dbo.links (
    id          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_links PRIMARY KEY,
    user_id     INT               NOT NULL
                CONSTRAINT FK_links_users REFERENCES dbo.users (id) ON DELETE CASCADE,
    url         NVARCHAR(2048)    NOT NULL,
    title       NVARCHAR(200)     NOT NULL,
    tags        NVARCHAR(200)     NOT NULL CONSTRAINT DF_links_tags DEFAULT (N''),  -- "school, tools"
    notes       NVARCHAR(MAX)     NOT NULL CONSTRAINT DF_links_notes DEFAULT (N''),
    is_pinned   BIT               NOT NULL CONSTRAINT DF_links_is_pinned DEFAULT (0),
    created_at  DATETIME2         NOT NULL CONSTRAINT DF_links_created_at DEFAULT (SYSUTCDATETIME())
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_links_user')
    CREATE INDEX IX_links_user ON dbo.links (user_id, is_pinned, created_at);
GO

/* ---------- views: ready-made queries the app (and you) can use -------- */

-- Every active subscription with how many days are left until it renews.
-- The reminder emails (Day 5) are picked from this view.
CREATE OR ALTER VIEW dbo.vw_upcoming_renewals AS
SELECT
    s.id               AS subscription_id,
    s.user_id,
    u.email,
    s.name,
    s.amount,
    s.currency,
    s.[cycle],
    s.next_renewal_at,
    s.remind_days,
    DATEDIFF(DAY, CAST(SYSUTCDATETIME() AS DATE), s.next_renewal_at) AS days_left
FROM dbo.subscriptions AS s
JOIN dbo.users         AS u ON u.id = s.user_id
WHERE s.status = N'active';
GO

-- What each user spends per month, per currency (weekly and yearly
-- subscriptions are converted to a monthly amount). Used by the dashboard.
CREATE OR ALTER VIEW dbo.vw_monthly_spend AS
SELECT
    user_id,
    currency,
    COUNT(*) AS active_subscriptions,
    CAST(SUM(CASE [cycle]
                 WHEN N'weekly' THEN amount * 52 / 12
                 WHEN N'yearly' THEN amount / 12
                 ELSE amount
             END) AS DECIMAL(12, 2)) AS monthly_total
FROM dbo.subscriptions
WHERE status = N'active'
GROUP BY user_id, currency;
GO

PRINT N'SubTrack schema is ready.';
GO
