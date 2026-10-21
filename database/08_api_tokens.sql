/* ==========================================================================
   AllOutFree (database SubTrack) — 08: API tokens for the Chrome extension

   Run after 07_bill_jobs.sql, in SSMS. Safe to run again; never deletes data.
   Keep in sync with app/models.py (ApiToken) and app/schema.py.

   Only the SHA-256 hash of each secret is stored. An active token holds one
   of five slots per user; the filtered unique index lets the database refuse
   a sixth one even when two requests arrive together. Revoked or expired
   tokens set slot to NULL (the filter ignores NULLs) and are kept.
   ========================================================================== */

USE SubTrack;
GO

IF OBJECT_ID(N'dbo.api_tokens', N'U') IS NULL
CREATE TABLE dbo.api_tokens (
    id            INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_api_tokens PRIMARY KEY,
    user_id       INT            NOT NULL
        CONSTRAINT FK_api_tokens_users REFERENCES dbo.users(id) ON DELETE CASCADE,
    name          NVARCHAR(60)   NOT NULL,
    token_hash    NVARCHAR(64)   NOT NULL,
    prefix        NVARCHAR(12)   NOT NULL,
    scopes        NVARCHAR(200)  NOT NULL,
    slot          INT            NULL
        CONSTRAINT CK_api_tokens_slot CHECK (slot BETWEEN 1 AND 5),
    created_at    DATETIME2(0)   NOT NULL CONSTRAINT DF_api_tokens_created DEFAULT (SYSUTCDATETIME()),
    last_used_at  DATETIME2(0)   NULL,
    expires_at    DATETIME2(0)   NOT NULL,
    revoked_at    DATETIME2(0)   NULL,
    CONSTRAINT UQ_api_tokens_hash UNIQUE (token_hash)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UX_api_tokens_user_slot')
    CREATE UNIQUE INDEX UX_api_tokens_user_slot ON dbo.api_tokens (user_id, slot)
        WHERE slot IS NOT NULL;
GO
