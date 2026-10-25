/* ==========================================================================
   AllOutFree (database SubTrack) — 10: cards in the Bills page card holder

   Run after 09_email_codes.sql, in SSMS. Safe to run again; never deletes data.
   Keep in sync with app/models.py (Card) and app/schema.py.

   Only the first 6 and last 4 digits of a card are stored (what a receipt
   shows), never the full number, expiry date or CVV. Removing a card sets
   removed_at; the row is kept.
   ========================================================================== */

USE SubTrack;
GO

IF OBJECT_ID(N'dbo.cards', N'U') IS NULL
CREATE TABLE dbo.cards (
    id          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_cards PRIMARY KEY,
    user_id     INT           NOT NULL
        CONSTRAINT FK_cards_users REFERENCES dbo.users(id) ON DELETE CASCADE,
    name        NVARCHAR(60)  NOT NULL,
    kind        NVARCHAR(10)  NOT NULL CONSTRAINT DF_cards_kind DEFAULT (N'credit')
        CONSTRAINT CK_cards_kind CHECK (kind IN (N'credit', N'debit')),
    first6      NVARCHAR(6)   NOT NULL
        CONSTRAINT CK_cards_first6 CHECK (LEN(first6) = 6 AND first6 NOT LIKE N'%[^0-9]%'),
    last4       NVARCHAR(4)   NOT NULL
        CONSTRAINT CK_cards_last4 CHECK (LEN(last4) = 4 AND last4 NOT LIKE N'%[^0-9]%'),
    color       NVARCHAR(10)  NOT NULL CONSTRAINT DF_cards_color DEFAULT (N'violet'),
    created_at  DATETIME2(0)  NOT NULL CONSTRAINT DF_cards_created DEFAULT (SYSUTCDATETIME()),
    removed_at  DATETIME2(0)  NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_cards_user')
    CREATE INDEX IX_cards_user ON dbo.cards (user_id, removed_at);
GO
