/* ==========================================================================
   SubTrack — 03: reminder settings, several lead times, renewal history

   Run after 02_accounts.sql, in SSMS. Safe to run again; never deletes data.
   Keep in sync with app/models.py (User, Subscription, Renewal, Reminder)
   and app/migrate.py.

   reminder_logs (from 01) stays as it is but is no longer used: it allowed
   only one reminder per renewal, and the new `reminders` table allows one
   per renewal + channel + "days before".
   ========================================================================== */

USE SubTrack;
GO

/* ---------- users: reminder settings ----------------------------------- */
IF COL_LENGTH(N'dbo.users', N'timezone') IS NULL
    ALTER TABLE dbo.users ADD timezone NVARCHAR(64) NOT NULL
        CONSTRAINT DF_users_timezone DEFAULT (N'UTC');
GO
IF COL_LENGTH(N'dbo.users', N'reminders_enabled') IS NULL
    ALTER TABLE dbo.users ADD reminders_enabled BIT NOT NULL
        CONSTRAINT DF_users_reminders_enabled DEFAULT (1);
GO
IF COL_LENGTH(N'dbo.users', N'reminder_hour') IS NULL
    ALTER TABLE dbo.users ADD reminder_hour INT NOT NULL
        CONSTRAINT DF_users_reminder_hour DEFAULT (9)
        CONSTRAINT CK_users_reminder_hour CHECK (reminder_hour BETWEEN 0 AND 23);
GO
IF COL_LENGTH(N'dbo.users', N'reminder_channels') IS NULL
    ALTER TABLE dbo.users ADD reminder_channels NVARCHAR(60) NOT NULL
        CONSTRAINT DF_users_reminder_channels DEFAULT (N'email');
GO

/* ---------- subscriptions: billing day, lead times, manage link -------- */
IF COL_LENGTH(N'dbo.subscriptions', N'billing_day') IS NULL
    ALTER TABLE dbo.subscriptions ADD billing_day INT NULL
        CONSTRAINT CK_subscriptions_billing_day CHECK (billing_day BETWEEN 1 AND 31);
GO
IF COL_LENGTH(N'dbo.subscriptions', N'lead_days') IS NULL
    ALTER TABLE dbo.subscriptions ADD lead_days NVARCHAR(40) NOT NULL
        CONSTRAINT DF_subscriptions_lead_days DEFAULT (N'7');
GO
IF COL_LENGTH(N'dbo.subscriptions', N'manage_url') IS NULL
    ALTER TABLE dbo.subscriptions ADD manage_url NVARCHAR(2048) NOT NULL
        CONSTRAINT DF_subscriptions_manage_url DEFAULT (N'');
GO

-- Older subscriptions keep their single "remind days" and their billing day.
UPDATE dbo.subscriptions
SET lead_days = CAST(remind_days AS NVARCHAR(40))
WHERE lead_days = N'7' AND remind_days <> 7;
GO
UPDATE dbo.subscriptions SET billing_day = DAY(next_renewal_at) WHERE billing_day IS NULL;
GO

/* ---------- renewals: passed renewal dates = expected charges ---------- */
IF OBJECT_ID(N'dbo.renewals', N'U') IS NULL
CREATE TABLE dbo.renewals (
    id               INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_renewals PRIMARY KEY,
    subscription_id  INT               NOT NULL
                     CONSTRAINT FK_renewals_subscriptions REFERENCES dbo.subscriptions (id) ON DELETE CASCADE,
    user_id          INT               NOT NULL,
    due_date         DATE              NOT NULL,
    amount           DECIMAL(10, 2)    NOT NULL,
    currency         NVARCHAR(8)       NOT NULL,
    status           NVARCHAR(20)      NOT NULL CONSTRAINT DF_renewals_status DEFAULT (N'expected')
                     CONSTRAINT CK_renewals_status CHECK (status IN (N'expected', N'paid', N'skipped')),
    created_at       DATETIME2         NOT NULL CONSTRAINT DF_renewals_created_at DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT UQ_renewals_once UNIQUE (subscription_id, due_date)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_renewals_user_date')
    CREATE INDEX IX_renewals_user_date ON dbo.renewals (user_id, due_date);
GO

/* ---------- reminders: one row per reminder to send -------------------- */
IF OBJECT_ID(N'dbo.reminders', N'U') IS NULL
CREATE TABLE dbo.reminders (
    id               INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_reminders PRIMARY KEY,
    subscription_id  INT               NOT NULL
                     CONSTRAINT FK_reminders_subscriptions REFERENCES dbo.subscriptions (id) ON DELETE CASCADE,
    user_id          INT               NOT NULL,
    renewal_date     DATE              NOT NULL,
    lead_days        INT               NOT NULL CONSTRAINT CK_reminders_lead CHECK (lead_days BETWEEN 0 AND 365),
    channel          NVARCHAR(20)      NOT NULL CONSTRAINT DF_reminders_channel DEFAULT (N'email'),
    status           NVARCHAR(20)      NOT NULL CONSTRAINT DF_reminders_status DEFAULT (N'pending')
                     CONSTRAINT CK_reminders_status
                     CHECK (status IN (N'pending', N'sending', N'sent', N'failed', N'skipped')),
    attempts         INT               NOT NULL CONSTRAINT DF_reminders_attempts DEFAULT (0),
    next_try_at      DATETIME2         NOT NULL CONSTRAINT DF_reminders_next_try_at DEFAULT (SYSUTCDATETIME()),
    claimed_at       DATETIME2         NULL,
    claim_token      NVARCHAR(32)      NULL,
    sent_at          DATETIME2         NULL,
    last_error       NVARCHAR(200)     NOT NULL CONSTRAINT DF_reminders_last_error DEFAULT (N''),
    created_at       DATETIME2         NOT NULL CONSTRAINT DF_reminders_created_at DEFAULT (SYSUTCDATETIME()),
    -- The same reminder can be planned only once, even by two jobs at once.
    CONSTRAINT UQ_reminders_once UNIQUE (subscription_id, renewal_date, channel, lead_days)
);
GO
-- The job looks for rows to send by status and time.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_reminders_status')
    CREATE INDEX IX_reminders_status ON dbo.reminders (status, next_try_at);
GO

PRINT N'03_reminders: done.';
GO
