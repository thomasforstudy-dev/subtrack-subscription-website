/* ==========================================================================
   SubTrack — 06: bills, bill lines and uploaded documents

   Run after 05_reminder_payload.sql, in SSMS. Safe to run again; never
   deletes data. Keep in sync with app/models.py (Document, Bill, BillLine).

   Files are NOT stored in the database: documents.stored_name is a random
   file name in the app's instance\uploads folder.
   Only the last 4 card digits are ever stored (no full number, PIN or OTP).
   ========================================================================== */

USE SubTrack;
GO

/* ---------- documents: uploaded photos / PDFs / Word files ------------- */
IF OBJECT_ID(N'dbo.documents', N'U') IS NULL
CREATE TABLE dbo.documents (
    id             INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_documents PRIMARY KEY,
    user_id        INT            NOT NULL
        CONSTRAINT FK_documents_users REFERENCES dbo.users(id) ON DELETE CASCADE,
    original_name  NVARCHAR(255)  NOT NULL,
    stored_name    NVARCHAR(64)   NOT NULL CONSTRAINT UQ_documents_stored_name UNIQUE,
    kind           NVARCHAR(10)   NOT NULL
        CONSTRAINT CK_documents_kind CHECK (kind IN (N'png', N'jpeg', N'webp', N'pdf', N'docx')),
    size_bytes     INT            NOT NULL CONSTRAINT CK_documents_size CHECK (size_bytes > 0),
    sha256         NVARCHAR(64)   NOT NULL,
    page_count     INT            NULL,
    status         NVARCHAR(20)   NOT NULL CONSTRAINT DF_documents_status DEFAULT (N'uploaded'),
    created_at     DATETIME2(0)   NOT NULL CONSTRAINT DF_documents_created DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT UQ_documents_once UNIQUE (user_id, sha256)
);
GO

/* ---------- bills: receipts and credit card bills ---------------------- */
IF OBJECT_ID(N'dbo.bills', N'U') IS NULL
CREATE TABLE dbo.bills (
    id                INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bills PRIMARY KEY,
    user_id           INT            NOT NULL
        CONSTRAINT FK_bills_users REFERENCES dbo.users(id) ON DELETE CASCADE,
    -- NO ACTION: SQL Server allows only one cascade path from users.
    document_id       INT            NULL
        CONSTRAINT FK_bills_documents REFERENCES dbo.documents(id),
    kind              NVARCHAR(20)   NOT NULL CONSTRAINT DF_bills_kind DEFAULT (N'receipt')
        CONSTRAINT CK_bills_kind CHECK (kind IN (N'receipt', N'card_bill')),
    merchant          NVARCHAR(200)  NOT NULL,
    branch            NVARCHAR(200)  NOT NULL CONSTRAINT DF_bills_branch DEFAULT (N''),
    address           NVARCHAR(500)  NOT NULL CONSTRAINT DF_bills_address DEFAULT (N''),
    invoice_number    NVARCHAR(64)   NOT NULL CONSTRAINT DF_bills_invoice_number DEFAULT (N''),
    invoice_date      DATE           NULL,
    transaction_date  DATE           NULL,
    transaction_time  TIME(0)        NULL,   -- NULL when the bill shows no time
    timezone          NVARCHAR(64)   NOT NULL CONSTRAINT DF_bills_timezone DEFAULT (N''),
    currency          NVARCHAR(8)    NOT NULL,
    subtotal          DECIMAL(12,2)  NULL,
    tax               DECIMAL(12,2)  NULL,
    total             DECIMAL(12,2)  NULL,
    category          NVARCHAR(30)   NOT NULL CONSTRAINT DF_bills_category DEFAULT (N'other'),
    card_last4        NVARCHAR(4)    NOT NULL CONSTRAINT DF_bills_card_last4 DEFAULT (N'')
        CONSTRAINT CK_bills_card_last4 CHECK (card_last4 = N'' OR card_last4 LIKE N'[0-9][0-9][0-9][0-9]'),
    statement_start   DATE           NULL,
    statement_end     DATE           NULL,
    due_date          DATE           NULL,
    paid_at           DATE           NULL,
    notes             NVARCHAR(MAX)  NOT NULL CONSTRAINT DF_bills_notes DEFAULT (N''),
    source            NVARCHAR(20)   NOT NULL CONSTRAINT DF_bills_source DEFAULT (N'manual'),
    status            NVARCHAR(20)   NOT NULL CONSTRAINT DF_bills_status DEFAULT (N'confirmed')
        CONSTRAINT CK_bills_status CHECK (status IN (N'confirmed', N'archived')),
    created_at        DATETIME2(0)   NOT NULL CONSTRAINT DF_bills_created DEFAULT (SYSUTCDATETIME()),
    updated_at        DATETIME2(0)   NOT NULL CONSTRAINT DF_bills_updated DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT CK_bills_money CHECK (
        (subtotal IS NULL OR subtotal >= 0) AND (tax IS NULL OR tax >= 0) AND (total IS NULL OR total >= 0)
    ),
    CONSTRAINT CK_bills_statement CHECK (
        statement_start IS NULL OR statement_end IS NULL OR statement_end >= statement_start
    )
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_bills_user_date')
    CREATE INDEX IX_bills_user_date ON dbo.bills (user_id, status, transaction_date);
GO

/* ---------- bill_lines: the items on a bill ---------------------------- */
IF OBJECT_ID(N'dbo.bill_lines', N'U') IS NULL
CREATE TABLE dbo.bill_lines (
    id           INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bill_lines PRIMARY KEY,
    bill_id      INT            NOT NULL
        CONSTRAINT FK_bill_lines_bills REFERENCES dbo.bills(id) ON DELETE CASCADE,
    position     INT            NOT NULL,
    description  NVARCHAR(300)  NOT NULL,
    quantity     DECIMAL(10,3)  NULL,
    unit_price   DECIMAL(12,2)  NULL,
    amount       DECIMAL(12,2)  NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_bill_lines_bill')
    CREATE INDEX IX_bill_lines_bill ON dbo.bill_lines (bill_id, position);
GO
