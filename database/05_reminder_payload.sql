/* Persist the first attempted email before delivery, so crash retries keep the
   same recipient, subject, body, sender, reply-to and idempotency key.
   Run after 04_links.sql. Additive and safe to run twice. */
USE SubTrack;
GO
IF COL_LENGTH(N'dbo.reminders', N'payload_json') IS NULL
    ALTER TABLE dbo.reminders ADD payload_json NVARCHAR(MAX) NULL;
GO
