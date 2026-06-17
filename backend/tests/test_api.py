import io
from datetime import datetime, timedelta
import pytest
from app.core import security
from app.models.models import User, Workspace, Note, Recording, Transcript, StructuredSummary, Tag

def test_core_security():
    password = "my-secure-password"
    hashed = security.get_password_hash(password)
    assert hashed != password
    assert security.verify_password(password, hashed) is True
    assert security.verify_password("wrong-password", hashed) is False

    data = {"sub": "user-123"}
    access = security.create_access_token(data)
    decoded = security.decode_token(access)
    assert decoded.get("sub") == "user-123"
    assert decoded.get("type") == "access"

    refresh = security.create_refresh_token(data)
    decoded_refresh = security.decode_token(refresh)
    assert decoded_refresh.get("sub") == "user-123"
    assert decoded_refresh.get("type") == "refresh"

def test_auth_flow(client):
    email = "newuser@example.com"
    password = "secretpassword"
    
    # 1. Register
    response = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "display_name": "New User"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == email
    assert data["user"]["display_name"] == "New User"
    
    # 2. Register again (should fail)
    response_dup = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password
    })
    assert response_dup.status_code == 400
    
    # 3. Login
    response_login = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert response_login.status_code == 200
    login_data = response_login.json()
    assert "access_token" in login_data
    access_token = login_data["access_token"]
    refresh_token = login_data["refresh_token"]
    
    # 4. Refresh token
    response_refresh = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert response_refresh.status_code == 200
    refresh_data = response_refresh.json()
    assert "access_token" in refresh_data
    
    # 5. Logout
    response_logout = client.post("/api/v1/auth/logout", json={
        "refresh_token": refresh_token
    })
    assert response_logout.status_code == 200

def test_oauth_google(client):
    response = client.post("/api/v1/auth/oauth/google", json={
        "token": "mock-google-oauth@example.com",
        "display_name": "Google User"
    })
    assert response.status_code == 200
    data = response.json()
    # Should resolve to mock email and details
    assert data["user"]["email"] == "oauth@example.com"
    assert data["user"]["display_name"] == "Oauth"

def test_oauth_apple(client):
    response = client.post("/api/v1/auth/oauth/apple", json={
        "token": "mock-apple-oauth2@example.com",
        "display_name": "Apple User"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "oauth2@example.com"

def test_workspaces_crud(client):
    # Register and login
    email = "workspace@example.com"
    password = "secretpassword"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create Workspace
    response = client.post("/api/v1/workspaces/", json={"name": "My Workspace"}, headers=headers)
    assert response.status_code == 200
    workspace = response.json()
    assert workspace["name"] == "My Workspace"
    workspace_id = workspace["id"]
    
    # Get Workspaces List
    list_res = client.get("/api/v1/workspaces/", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
    
    # Get Workspace by ID
    get_res = client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "My Workspace"
    
    # Delete Workspace
    del_res = client.delete(f"/api/v1/workspaces/{workspace_id}", headers=headers)
    assert del_res.status_code == 204
    
    # Get Workspace after delete should fail
    get_res_deleted = client.get(f"/api/v1/workspaces/{workspace_id}", headers=headers)
    assert get_res_deleted.status_code == 404

def test_notes_crud_and_related_entities(client):
    # Register and login
    email = "notes@example.com"
    password = "secretpassword"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create Workspace
    ws_res = client.post("/api/v1/workspaces/", json={"name": "Notes WS"}, headers=headers)
    workspace_id = ws_res.json()["id"]
    
    # 1. Create Note
    note_payload = {
        "title": "Meeting Note",
        "duration_sec": 120,
        "file_path": "/fake/path/audio.m4a",
        "status": "completed",
        "workspace_id": workspace_id
    }
    response = client.post("/api/v1/notes/", json=note_payload, headers=headers)
    assert response.status_code == 200
    note = response.json()
    assert note["title"] == "Meeting Note"
    note_id = note["id"]
    
    # 2. Get Notes List
    list_res = client.get("/api/v1/notes/", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
    
    # 3. Update Note
    update_res = client.put(f"/api/v1/notes/{note_id}", json={"title": "Updated Meeting Note"}, headers=headers)
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Updated Meeting Note"
    
    # 4. Add Tags
    tags_res = client.post(f"/api/v1/notes/{note_id}/tags", json=["meeting", "work"], headers=headers)
    assert tags_res.status_code == 200
    assert "meeting" in tags_res.json()["tags"]
    
    # 5. Upload Audio / Recording
    audio_file = io.BytesIO(b"fake audio data content")
    upload_res = client.post(
        f"/api/v1/recordings/upload?note_id={note_id}",
        files={"file": ("test_audio.m4a", audio_file, "audio/m4a")},
        headers=headers
    )
    assert upload_res.status_code == 200
    recording = upload_res.json()
    assert recording["note_id"] == note_id
    recording_id = recording["id"]
    
    # 6. Retrieve Recording
    rec_res = client.get(f"/api/v1/recordings/{recording_id}", headers=headers)
    assert rec_res.status_code == 200
    assert rec_res.json()["id"] == recording_id
    
    # 7. Create and get Transcript
    transcript_res = client.post("/api/v1/transcripts/", json={
        "note_id": note_id,
        "text": "Hello this is a meeting transcript text.",
        "confidence": 0.95
    }, headers=headers)
    assert transcript_res.status_code == 200
    assert transcript_res.json()["text"] == "Hello this is a meeting transcript text."
    
    get_trans_res = client.get(f"/api/v1/transcripts/{note_id}", headers=headers)
    assert get_trans_res.status_code == 200
    assert get_trans_res.json()["text"] == "Hello this is a meeting transcript text."
    
    # 8. Get summaries (none exist yet since we haven't generated any via AI)
    get_sum_res = client.get(f"/api/v1/summaries/{note_id}", headers=headers)
    assert get_sum_res.status_code == 200
    assert get_sum_res.json() == []  # empty list, no AI summaries generated
    
    # 9. Delete Note
    del_res = client.delete(f"/api/v1/notes/{note_id}", headers=headers)
    assert del_res.status_code == 204
    
    # 10. Get Deleted Note should fail
    get_res_deleted = client.get(f"/api/v1/notes/{note_id}", headers=headers)
    assert get_res_deleted.status_code == 404

def test_s3_storage_key_ownership_idor(client):
    # 1. Register User A and User B
    client.post("/api/v1/auth/register", json={"email": "usera@example.com", "password": "password123"})
    login_a = client.post("/api/v1/auth/login", json={"email": "usera@example.com", "password": "password123"}).json()
    token_a = login_a["access_token"]
    user_a_id = login_a["user"]["id"]

    client.post("/api/v1/auth/register", json={"email": "userb@example.com", "password": "password123"})
    login_b = client.post("/api/v1/auth/login", json={"email": "userb@example.com", "password": "password123"}).json()
    token_b = login_b["access_token"]
    user_b_id = login_b["user"]["id"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 2. User A gets a valid key
    upload_res = client.get("/api/v1/storage/presign-upload?purpose=audio&extension=m4a", headers=headers_a)
    assert upload_res.status_code == 200
    key_a = upload_res.json()["key"]
    assert f"audio/{user_a_id}/" in key_a

    # 3. User B tries to download User A's key (Should be rejected with 403)
    download_res = client.get(f"/api/v1/storage/presign-download?key={key_a}", headers=headers_b)
    assert download_res.status_code == 403
    assert "Access denied" in download_res.json()["detail"]

    # 4. User A successfully accesses their own key
    download_ok = client.get(f"/api/v1/storage/presign-download?key={key_a}", headers=headers_a)
    assert download_ok.status_code == 200

