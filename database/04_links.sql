/* ==========================================================================
   SubTrack — 04: duplicate check and site icons for pinned links

   Run after 03_reminders.sql, in SSMS. Safe to run again; never deletes data.
   Keep in sync with app/models.py (Link) and app/migrate.py.

   After running it, fill in the fingerprints of older links (they are made
   by Python, so they match exactly what the app computes):
       .venv\Scripts\python -m flask --app app fill-link-fingerprints
   ========================================================================== */

USE SubTrack;
GO

-- SHA-256 of the cleaned-up address. Not UNIQUE: links saved before this
-- script may already have duplicates, and those must not be deleted.
IF COL_LENGTH(N'dbo.links', N'url_hash') IS NULL
    ALTER TABLE dbo.links ADD url_hash NVARCHAR(64) NULL;
GO

IF COL_LENGTH(N'dbo.links', N'favicon_url') IS NULL
    ALTER TABLE dbo.links ADD favicon_url NVARCHAR(2048) NOT NULL
        CONSTRAINT DF_links_favicon_url DEFAULT (N'');
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_links_user_hash')
    CREATE INDEX IX_links_user_hash ON dbo.links (user_id, url_hash);
GO

PRINT N'04_links: done. Now run: flask --app app fill-link-fingerprints';
GO
