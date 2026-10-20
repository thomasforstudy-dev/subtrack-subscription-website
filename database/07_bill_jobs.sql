/* ==========================================================================
   SubTrack — 07: reading uploaded bills (jobs, page text, drafts, history)

   Run after 06_bills.sql, in SSMS. Safe to run again; never deletes data.
   Keep in sync with app/models.py (DocumentJob, DocumentPage, BillDraft,
   BillDraftRevision) and app/schema.py.

   SQL Server allows only one cascade path to a table, so only the links to
   users cascade; the links to documents/jobs/bills are NO ACTION.
   ========================================================================== */

USE SubTrack;
GO

/* ---------- document_jobs: one "read this bill" job per file ----------- */
IF OBJECT_ID(N'dbo.document_jobs', N'U') IS NULL
CREATE TABLE dbo.document_jobs (
    id           INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_document_jobs PRIMARY KEY,
    user_id      INT           NOT NULL
        CONSTRAINT FK_document_jobs_users REFERENCES dbo.users(id) ON DELETE CASCADE,
    document_id  INT           NOT NULL
        CONSTRAINT FK_document_jobs_documents REFERENCES dbo.documents(id),
    status       NVARCHAR(20)  NOT NULL CONSTRAINT DF_document_jobs_status DEFAULT (N'queued')
        CONSTRAINT CK_document_jobs_status CHECK (status IN (N'queued', N'running', N'succeeded', N'failed')),
    attempts     INT           NOT NULL CONSTRAINT DF_document_jobs_attempts DEFAULT (0)
        CONSTRAINT CK_document_jobs_attempts CHECK (attempts >= 0),
    next_try_at  DATETIME2(0)  NOT NULL CONSTRAINT DF_document_jobs_next DEFAULT (SYSUTCDATETIME()),
    claim_token  NVARCHAR(32)  NULL,
    claimed_at   DATETIME2(0)  NULL,
    finished_at  DATETIME2(0)  NULL,
    error_code   NVARCHAR(40)  NOT NULL CONSTRAINT DF_document_jobs_error DEFAULT (N''),
    created_at   DATETIME2(0)  NOT NULL CONSTRAINT DF_document_jobs_created DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT UQ_document_jobs_document UNIQUE (document_id)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_document_jobs_status')
    CREATE INDEX IX_document_jobs_status ON dbo.document_jobs (status, next_try_at);
GO

/* ---------- document_pages: the text read from each page -------------- */
IF OBJECT_ID(N'dbo.document_pages', N'U') IS NULL
CREATE TABLE dbo.document_pages (
    id           INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_document_pages PRIMARY KEY,
    document_id  INT            NOT NULL
        CONSTRAINT FK_document_pages_documents REFERENCES dbo.documents(id),
    user_id      INT            NOT NULL,
    page_number  INT            NOT NULL CONSTRAINT CK_document_pages_number CHECK (page_number >= 1),
    text         NVARCHAR(MAX)  NOT NULL CONSTRAINT DF_document_pages_text DEFAULT (N''),
    source       NVARCHAR(20)   NOT NULL
        CONSTRAINT CK_document_pages_source CHECK (source IN (N'pdf-text', N'docx', N'ocr')),
    engine       NVARCHAR(80)   NOT NULL CONSTRAINT DF_document_pages_engine DEFAULT (N''),
    truncated    BIT            NOT NULL CONSTRAINT DF_document_pages_truncated DEFAULT (0),
    created_at   DATETIME2(0)   NOT NULL CONSTRAINT DF_document_pages_created DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT UQ_document_pages_once UNIQUE (document_id, page_number)
);
GO

/* ---------- bill_drafts: found values waiting for the owner's check ---- */
IF OBJECT_ID(N'dbo.bill_drafts', N'U') IS NULL
CREATE TABLE dbo.bill_drafts (
    id              INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bill_drafts PRIMARY KEY,
    user_id         INT            NOT NULL
        CONSTRAINT FK_bill_drafts_users REFERENCES dbo.users(id) ON DELETE CASCADE,
    document_id     INT            NOT NULL
        CONSTRAINT FK_bill_drafts_documents REFERENCES dbo.documents(id),
    job_id          INT            NOT NULL
        CONSTRAINT FK_bill_drafts_jobs REFERENCES dbo.document_jobs(id),
    status          NVARCHAR(20)   NOT NULL CONSTRAINT DF_bill_drafts_status DEFAULT (N'draft')
        CONSTRAINT CK_bill_drafts_status CHECK (status IN (N'draft', N'accepted', N'discarded')),
    extractor       NVARCHAR(80)   NOT NULL,
    extracted_json  NVARCHAR(MAX)  NOT NULL,
    values_json     NVARCHAR(MAX)  NOT NULL,
    revision        INT            NOT NULL CONSTRAINT DF_bill_drafts_revision DEFAULT (1),
    bill_id         INT            NULL
        CONSTRAINT FK_bill_drafts_bills REFERENCES dbo.bills(id),
    created_at      DATETIME2(0)   NOT NULL CONSTRAINT DF_bill_drafts_created DEFAULT (SYSUTCDATETIME()),
    updated_at      DATETIME2(0)   NOT NULL CONSTRAINT DF_bill_drafts_updated DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT UQ_bill_drafts_job UNIQUE (job_id)
);
GO

/* ---------- bill_draft_revisions: the history of every change --------- */
IF OBJECT_ID(N'dbo.bill_draft_revisions', N'U') IS NULL
CREATE TABLE dbo.bill_draft_revisions (
    id           INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_bill_draft_revisions PRIMARY KEY,
    draft_id     INT            NOT NULL
        CONSTRAINT FK_bill_draft_revisions_drafts REFERENCES dbo.bill_drafts(id) ON DELETE CASCADE,
    user_id      INT            NOT NULL,
    number       INT            NOT NULL,
    action       NVARCHAR(20)   NOT NULL
        CONSTRAINT CK_bill_draft_revisions_action CHECK (action IN (N'extracted', N'edited', N'accepted')),
    changed      NVARCHAR(400)  NOT NULL CONSTRAINT DF_bill_draft_revisions_changed DEFAULT (N''),
    values_json  NVARCHAR(MAX)  NOT NULL,
    created_at   DATETIME2(0)   NOT NULL CONSTRAINT DF_bill_draft_revisions_created DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT UQ_bill_draft_revisions_number UNIQUE (draft_id, number)
);
GO
