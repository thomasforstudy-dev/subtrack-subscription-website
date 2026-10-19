/* ==========================================================================
   SubTrack — 02: usernames, email confirmation, one-time email links

   Run after 01_schema.sql, in SSMS (File > Open > this file > Execute).
   Safe to run again: every step checks first. It never deletes data.
   Keep in sync with app/models.py (User, AuthToken) and app/migrate.py.
   ========================================================================== */

USE SubTrack;
GO

/* ---------- users.username --------------------------------------------- */
IF COL_LENGTH(N'dbo.users', N'username') IS NULL
    ALTER TABLE dbo.users ADD username NVARCHAR(30) NULL;
GO

-- Accounts made before usernames existed get "user_<id>" (same rule as
-- app/migrate.py for SQLite). User ids are unique, so these are too.
UPDATE dbo.users SET username = CONCAT(N'user_', id) WHERE username IS NULL;
GO

IF EXISTS (SELECT 1 FROM sys.columns
           WHERE object_id = OBJECT_ID(N'dbo.users') AND name = N'username' AND is_nullable = 1)
    ALTER TABLE dbo.users ALTER COLUMN username NVARCHAR(30) NOT NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.key_constraints WHERE name = N'UQ_users_username')
    ALTER TABLE dbo.users ADD CONSTRAINT UQ_users_username UNIQUE (username);
GO

-- Same rule as app/validation.py: 3-30 of a-z, 0-9, _ (binary collation so
-- upper-case letters don't slip through the case-insensitive default).
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_users_username')
    ALTER TABLE dbo.users ADD CONSTRAINT CK_users_username CHECK (
        LEN(username) BETWEEN 3 AND 30
        AND username COLLATE Latin1_General_BIN NOT LIKE N'%[^a-z0-9_]%'
    );
GO

/* ---------- users.email_verified_at ------------------------------------ */
IF COL_LENGTH(N'dbo.users', N'email_verified_at') IS NULL
    ALTER TABLE dbo.users ADD email_verified_at DATETIME2 NULL;  -- empty = not confirmed yet
GO

/* ---------- auth_tokens: one-time links sent by email ------------------ */
IF OBJECT_ID(N'dbo.auth_tokens', N'U') IS NULL
CREATE TABLE dbo.auth_tokens (
    id          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_auth_tokens PRIMARY KEY,
    user_id     INT               NOT NULL
                CONSTRAINT FK_auth_tokens_users REFERENCES dbo.users (id) ON DELETE CASCADE,
    purpose     NVARCHAR(20)      NOT NULL
                CONSTRAINT CK_auth_tokens_purpose CHECK (purpose IN (N'verify_email', N'reset_password')),
    token_hash  NVARCHAR(64)      NOT NULL CONSTRAINT UQ_auth_tokens_hash UNIQUE,  -- SHA-256, never the token
    email       NVARCHAR(255)     NOT NULL,   -- the address the link was sent to
    created_at  DATETIME2         NOT NULL CONSTRAINT DF_auth_tokens_created_at DEFAULT (SYSUTCDATETIME()),
    expires_at  DATETIME2         NOT NULL,
    used_at     DATETIME2         NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_auth_tokens_user')
    CREATE INDEX IX_auth_tokens_user ON dbo.auth_tokens (user_id, purpose, used_at);
GO

PRINT N'02_accounts: done.';
GO
