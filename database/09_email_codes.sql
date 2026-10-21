/* ==========================================================================
   AllOutFree (database SubTrack) — 09: 6-digit codes in the confirm email

   Run after 08_api_tokens.sql, in SSMS. Safe to run again; never deletes data.
   Keep in sync with app/models.py (EmailCode) and app/schema.py.

   A separate table from auth_tokens, so a short code can never be used as an
   email link. Only the SHA-256 of "user id:code" is stored.
   ========================================================================== */

USE SubTrack;
GO

IF OBJECT_ID(N'dbo.email_codes', N'U') IS NULL
CREATE TABLE dbo.email_codes (
    id          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_email_codes PRIMARY KEY,
    user_id     INT            NOT NULL
        CONSTRAINT FK_email_codes_users REFERENCES dbo.users(id) ON DELETE CASCADE,
    code_hash   NVARCHAR(64)   NOT NULL,
    email       NVARCHAR(255)  NOT NULL,
    created_at  DATETIME2(0)   NOT NULL CONSTRAINT DF_email_codes_created DEFAULT (SYSUTCDATETIME()),
    expires_at  DATETIME2(0)   NOT NULL,
    used_at     DATETIME2(0)   NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_email_codes_user')
    CREATE INDEX IX_email_codes_user ON dbo.email_codes (user_id, used_at);
GO
