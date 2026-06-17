import pytest
from datetime import datetime, timedelta
import json
from app.models.models import Note, Transcript, StructuredSummary, Tag, DeletedRecord

def test_sync_push_and_pull(client, db):
    # 1. Register and login
    email = "sync@example.com"
    password = "secretpassword"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Push client changes (CREATE note)
    note_id = "local-uuid-1"
    note_payload = {
        "id": note_id,
        "title": "Offline meeting note",
        "durationSec": 100,
        "filePath": "/local/path/1.m4a",
        "status": "completed",
        "transcription": "Offline transcript text",
        "summary": "Offline summary text",
        "tags": ["offline", "meeting"]
    }
    
    sync_request = {
        "last_sync_timestamp": None,
        "client_changes": [
            {
                "id": 1,
                "action": "CREATE",
                "table_name": "notes",
                "record_id": note_id,
                "payload": json.dumps(note_payload),
                "created_at": (datetime.utcnow() - timedelta(minutes=5)).isoformat()
            }
        ]
    }

    res = client.post("/api/v1/sync/", json=sync_request, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert 1 in data["processed_client_task_ids"]
    assert len(data["server_changes"]) == 1
    assert data["server_changes"][0]["id"] == note_id
    assert data["server_changes"][0]["title"] == "Offline meeting note"
    assert data["server_changes"][0]["transcription"] == "Offline transcript text"

    # Verify note was created in database
    db_note = db.query(Note).filter(Note.id == note_id).first()
    assert db_note is not None
    assert db_note.title == "Offline meeting note"
    
    # 3. Pull delta changes (CREATE on another device)
    last_sync = data["server_timestamp"]
    
    # Verify no new changes if nothing is added
    res_no_delta = client.post("/api/v1/sync/", json={"last_sync_timestamp": last_sync, "client_changes": []}, headers=headers)
    assert res_no_delta.status_code == 200
    assert len(res_no_delta.json()["server_changes"]) == 0

def test_sync_conflict_resolution_lww(client, db):
    # 1. Register and login
    email = "conflict@example.com"
    password = "secretpassword"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Setup database note
    note_id = "conflict-note-uuid"
    note_payload = {
        "id": note_id,
        "title": "Initial note",
        "durationSec": 50,
        "filePath": "/path.m4a",
        "status": "completed"
    }
    
    # Push initial
    res_init = client.post("/api/v1/sync/", json={
        "last_sync_timestamp": None,
        "client_changes": [
            {
                "id": 1,
                "action": "CREATE",
                "table_name": "notes",
                "record_id": note_id,
                "payload": json.dumps(note_payload),
                "created_at": (datetime.utcnow() - timedelta(minutes=10)).isoformat()
            }
        ]
    }, headers=headers)
    assert res_init.status_code == 200
    last_sync = res_init.json()["server_timestamp"]

    # 3. Server changes update note (Server modification happens at minutes=5)
    db_note = db.query(Note).filter(Note.id == note_id).first()
    db_note.title = "Server modified title"
    db_note.updated_at = datetime.utcnow() - timedelta(minutes=5)
    db.commit()

    # 4. Client modification older than server (Client modification at minutes=8)
    client_payload_old = note_payload.copy()
    client_payload_old["title"] = "Client old update"
    
    res_old = client.post("/api/v1/sync/", json={
        "last_sync_timestamp": last_sync,
        "client_changes": [
            {
                "id": 2,
                "action": "UPDATE",
                "table_name": "notes",
                "record_id": note_id,
                "payload": json.dumps(client_payload_old),
                "created_at": (datetime.utcnow() - timedelta(minutes=8)).isoformat()
            }
        ]
    }, headers=headers)
    assert res_old.status_code == 200
    
    db.refresh(db_note)
    assert db_note.title == "Server modified title"

    # 5. Client modification newer than server (Client modification at minutes=2)
    client_payload_new = note_payload.copy()
    client_payload_new["title"] = "Client newer wins"
    
    res_new = client.post("/api/v1/sync/", json={
        "last_sync_timestamp": last_sync,
        "client_changes": [
            {
                "id": 3,
                "action": "UPDATE",
                "table_name": "notes",
                "record_id": note_id,
                "payload": json.dumps(client_payload_new),
                "created_at": (datetime.utcnow() - timedelta(minutes=2)).isoformat()
            }
        ]
    }, headers=headers)
    assert res_new.status_code == 200
    
    db.refresh(db_note)
    assert db_note.title == "Client newer wins"
