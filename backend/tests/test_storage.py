import pytest
from unittest.mock import patch, MagicMock

def test_presign_upload_and_download(client):
    # Register and login
    email = "storage-test@example.com"
    password = "secretpassword"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Presign single-file upload
    res = client.get("/api/v1/storage/presign-upload?purpose=audio&extension=m4a", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "url" in data
    assert "key" in data
    assert data["key"].startswith("audio/")
    assert data["key"].endswith(".m4a")

    # Invalid purpose
    res_invalid = client.get("/api/v1/storage/presign-upload?purpose=invalid&extension=m4a", headers=headers)
    assert res_invalid.status_code == 400

    # 2. Presign download
    res_download = client.get(f"/api/v1/storage/presign-download?key={data['key']}", headers=headers)
    assert res_download.status_code == 200
    assert "url" in res_download.json()

def test_multipart_flow(client):
    # Register and login
    email = "storage-multi@example.com"
    password = "secretpassword"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Initiate Multipart
    res_init = client.post("/api/v1/storage/multipart/initiate", json={
        "purpose": "audio",
        "extension": "wav"
    }, headers=headers)
    assert res_init.status_code == 200
    init_data = res_init.json()
    assert "upload_id" in init_data
    assert "key" in init_data
    key = init_data["key"]
    upload_id = init_data["upload_id"]

    # 2. Presign Parts
    res_parts = client.post("/api/v1/storage/multipart/presign-parts", json={
        "key": key,
        "upload_id": upload_id,
        "part_numbers": [1, 2]
    }, headers=headers)
    assert res_parts.status_code == 200
    parts_data = res_parts.json()
    assert len(parts_data["parts"]) == 2
    assert parts_data["parts"][0]["part_number"] == 1
    assert "url" in parts_data["parts"][0]

    # 3. Complete Multipart
    res_complete = client.post("/api/v1/storage/multipart/complete", json={
        "key": key,
        "upload_id": upload_id,
        "parts": [
            {"part_number": 1, "etag": "etag-chunk-1"},
            {"part_number": 2, "etag": "etag-chunk-2"}
        ]
    }, headers=headers)
    assert res_complete.status_code == 200
    assert "location" in res_complete.json()
    assert res_complete.json()["key"] == key

    # 4. Abort Multipart
    res_abort = client.post("/api/v1/storage/multipart/abort", json={
        "key": key,
        "upload_id": upload_id
    }, headers=headers)
    assert res_abort.status_code == 200
    assert res_abort.json()["status"] == "aborted"
