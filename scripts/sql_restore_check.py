"""COPY_ONLY backup + private uploads + new isolated restore; no source changes."""

import hashlib
import json
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.sql_preview import DATABASE, RESTORE_DATABASE, INSTANCE, access_details, build_app, dsn, snapshots


def execute(connection, sql, *parameters):
    cursor = connection.execute(sql, *parameters)
    while cursor.nextset():
        pass


def control(action):
    subprocess.run(["powershell", "-NoProfile", "-File", str(ROOT / "scripts/sql-preview-control.ps1"),
                    action, "-Python", sys.executable], cwd=ROOT, check=True,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def login(app, account):
    from tests.html_helpers import Page
    client = app.test_client()
    form = Page(client.get("/login").get_data(as_text=True)).form_with("identifier")["fields"]
    response = client.post("/login", data={"identifier": account["username"], "password": account["password"],
                                         "csrf_token": form["csrf_token"]})
    if response.status_code != 302:
        raise RuntimeError("Restored application login failed")
    return client


def run():
    suffix = secrets.token_hex(8)
    target = INSTANCE / ("sql-restore-" + suffix)
    target.mkdir(exist_ok=False)
    uploads = target / "uploads"
    uploads.mkdir()
    control("stop")  # no other server, task or Windows service is stopped
    try:
        source = build_app()
        from app import db
        from app.documents import file_path
        from app.models import Document, User
        before = snapshots(source)
        files = []
        with source.app_context():
            if User.query.filter(~User.email.endswith("@example.com")).count():
                raise RuntimeError("Source contains non-synthetic users; refusing backup drill")
            for document in Document.query.order_by(Document.id):
                path = file_path(document.stored_name).resolve()
                if not path.is_relative_to((INSTANCE / "uploads").resolve()):
                    raise RuntimeError("Document path escaped synthetic uploads")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest != document.sha256:
                    raise RuntimeError("Source file hash does not match its database mapping")
                shutil.copy2(path, uploads / document.stored_name)
                files.append({"document_id": document.id, "owner_id": document.user_id,
                              "stored_name": document.stored_name, "sha256": digest})

        with pyodbc.connect(dsn("master"), autocommit=True) as master:
            if master.execute("SELECT DB_ID(?)", RESTORE_DATABASE).fetchone()[0] is not None:
                raise RuntimeError("Restore target already exists; refusing to overwrite it")
            directories = master.execute(
                "SELECT CONVERT(nvarchar(4000),SERVERPROPERTY('InstanceDefaultBackupPath')),"
                "CONVERT(nvarchar(4000),SERVERPROPERTY('InstanceDefaultDataPath')),"
                "CONVERT(nvarchar(4000),SERVERPROPERTY('InstanceDefaultLogPath'))").fetchone()
            if not all(directories):
                raise RuntimeError("SQL Server default backup/data/log paths unavailable")
            backup = str(Path(directories[0]) / ("SubTrack_CodexPreview_" + suffix + ".bak"))
            data_path = str(Path(directories[1]) / (RESTORE_DATABASE + "_" + suffix + ".mdf"))
            log_path = str(Path(directories[2]) / (RESTORE_DATABASE + "_" + suffix + ".ldf"))
            exists = master.execute("DECLARE @path nvarchar(4000)=?; EXEC master.dbo.xp_fileexist @path", backup).fetchone()
            if exists[0]:
                raise RuntimeError("Backup filename exists; preserving it")
            execute(master, "DECLARE @path nvarchar(4000)=?; BACKUP DATABASE [SubTrack_CodexPreview_20261020] "
                    "TO DISK=@path WITH COPY_ONLY,CHECKSUM", backup)
            execute(master, "DECLARE @path nvarchar(4000)=?; RESTORE VERIFYONLY FROM DISK=@path WITH CHECKSUM", backup)
            cursor = master.execute("DECLARE @path nvarchar(4000)=?; RESTORE FILELISTONLY FROM DISK=@path", backup)
            names = [column[0] for column in cursor.description]
            parts = [dict(zip(names, row)) for row in cursor.fetchall()]
            while cursor.nextset():
                pass
            if sorted(row["Type"] for row in parts) != ["D", "L"]:
                raise RuntimeError("Unexpected backup file layout; review restore mapping manually")
            data_name = next(row["LogicalName"] for row in parts if row["Type"] == "D")
            log_name = next(row["LogicalName"] for row in parts if row["Type"] == "L")
            execute(master, "DECLARE @backup nvarchar(4000)=?,@dataName nvarchar(128)=?,@dataPath nvarchar(4000)=?,"
                    "@logName nvarchar(128)=?,@logPath nvarchar(4000)=?; "
                    "RESTORE DATABASE [SubTrack_CodexRestore_20261020] FROM DISK=@backup "
                    "WITH MOVE @dataName TO @dataPath,MOVE @logName TO @logPath,CHECKSUM,RECOVERY",
                    backup, data_name, data_path, log_name, log_path)
        restored = build_app(RESTORE_DATABASE, uploads=uploads)
        if snapshots(restored) != before or snapshots(source) != before:
            raise RuntimeError("Restore records mismatch or source records changed")
        with pyodbc.connect(dsn(RESTORE_DATABASE), autocommit=True) as connection:
            execute(connection, "DBCC CHECKDB ([SubTrack_CodexRestore_20261020]) WITH NO_INFOMSGS")
        for item in files:
            if hashlib.sha256((uploads / item["stored_name"]).read_bytes()).hexdigest() != item["sha256"]:
                raise RuntimeError("Restored upload hash mismatch")
        accounts = access_details()["accounts"]
        owner, other = login(restored, accounts[0]), login(restored, accounts[1])
        with restored.app_context():
            owner_id = User.query.filter_by(username=accounts[0]["username"]).one().id
        own_file = next(item for item in files if item["owner_id"] == owner_id)
        response = owner.get(f"/bills/files/{own_file['document_id']}")
        if response.status_code != 200 or hashlib.sha256(response.data).hexdigest() != own_file["sha256"]:
            raise RuntimeError("Restored file is unavailable through its owner route")
        if other.get(f"/bills/files/{own_file['document_id']}").status_code != 404:
            raise RuntimeError("Restored file ownership failed")
        if owner.get("/bills/export.json").status_code != 200:
            raise RuntimeError("Restored bill export failed")
        if snapshots(source) != before:
            raise RuntimeError("Source data changed during restored-app checks")
        result = {"source": DATABASE, "restore_target": RESTORE_DATABASE,
                  "backup": backup, "uploads_copy": str(uploads), "copy_only_checksum_backup": "passed",
                  "restore_verifyonly_checksum": "passed", "restored_tables_match": True,
                  "source_tables_unchanged": True, "checkdb": "passed", "private_files": files,
                  "file_hashes_owner_download_and_isolation": "passed", "tables": before,
                  "scope": "Synthetic SQL database plus private uploads; not a production restore claim"}
        (INSTANCE / "sql-restore-results.json").write_text(json.dumps(result, indent=2))
        print(json.dumps({"source": DATABASE, "restore_target": RESTORE_DATABASE,
                          "source_preserved": True, "files_verified": len(files), "checkdb": "passed"}))
    finally:
        control("start")


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        print("Synthetic restore drill failed: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
