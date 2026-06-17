import pytest
import os
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.models import User, Note, Transcript, StructuredSummary, MeetingMinutes, ScheduledEmail
from app.services.email_service import EmailService

def test_email_html_rendering(db: Session):
    # 1. Create a dummy note
    user = User(email="test_render@example.com", hashed_password="pw")
    db.add(user)
    db.commit()
    db.refresh(user)

    note = Note(title="Technical Alignment Sync", file_path="audio.mp3", user_id=user.id)
    db.add(note)
    db.commit()
    db.refresh(note)

    # Add transcript
    tr = Transcript(note_id=note.id, text="Let's align on database design and search patterns.")
    db.add(tr)

    # Add summary
    summary = StructuredSummary(
        note_id=note.id,
        summary_type="executive",
        structured_data='{"executive_summary": "Database search alignment session."}',
        provider="openai",
        model="gpt-4"
    )
    db.add(summary)

    # Add minutes
    minutes = MeetingMinutes(
        note_id=note.id,
        overview="Minutes overview description",
        agenda='["DB design", "pgvector"]',
        discussion_points='[{"topic": "pgvector", "summary": "Agreed to use SafeVector fallback"}]',
        decisions='["Use SafeVector"]',
        risks='["SQLite performance"]',
        action_items='[{"task": "Implement SafeVector", "owner": "John", "due_date": "Tomorrow"}]',
        provider="openai",
        model="gpt-4"
    )
    db.add(minutes)
    db.commit()
    db.refresh(note)

    # Render HTML
    html = EmailService.render_email_html(note, True, True, True)

    assert "Technical Alignment Sync" in html
    assert "Audio Transcript" in html
    assert "Let&#x27;s align on database design" in html
    assert "🤖 AI Summaries" in html
    assert "Database search alignment session" in html
    assert "Meeting Minutes" in html
    assert "Use SafeVector" in html
    assert "SQLite performance" in html
    assert "Implement SafeVector" in html

@pytest.mark.asyncio
async def test_mock_email_delivery_filesystem(db: Session):
    user = User(email="test_delivery@example.com", hashed_password="pw")
    db.add(user)
    db.commit()
    db.refresh(user)

    note = Note(title="Project Kickoff", file_path="audio.mp3", user_id=user.id)
    db.add(note)
    db.commit()
    db.refresh(note)

    # Clear previous mock sent emails
    if os.path.exists("sent_emails"):
        for f in os.listdir("sent_emails"):
            os.remove(os.path.join("sent_emails", f))

    html = EmailService.render_email_html(note, False, False, False)
    
    # Send mock email
    await EmailService.send_email(
        recipient="user@example.com",
        subject="Project Kickoff Share",
        html_content=html,
        provider="smtp"
    )

    # Assert file was dumped locally under sent_emails/
    assert os.path.exists("sent_emails")
    files = os.listdir("sent_emails")
    assert len(files) == 1
    assert "user@example.com" in files[0]
    assert "Project_Kickoff_Share" in files[0]

@pytest.mark.asyncio
async def test_email_api_endpoints_and_queue(client: TestClient, db: Session):
    # 1. Register and login
    email = "email_user@example.com"
    password = "secretpassword"
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login_res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch user
    user = db.query(User).filter(User.email == email).first()
    assert user is not None

    # Create note
    note = Note(title="API Test Note", file_path="path.mp3", user_id=user.id)
    db.add(note)
    db.commit()
    db.refresh(note)

    # 2. Test send-now endpoint
    send_payload = {
        "note_id": note.id,
        "recipient": "friend@example.com",
        "subject": "VoiceMind Share: API Test Note",
        "provider": "gmail",
        "include_transcript": True,
        "include_summary": True,
        "include_minutes": True
    }
    res = client.post("/api/v1/emails/send-now", json=send_payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # 3. Test schedule endpoint
    schedule_time = datetime.utcnow() + timedelta(minutes=5)
    schedule_payload = {
        "note_id": note.id,
        "recipient": "scheduled_friend@example.com",
        "subject": "VoiceMind Scheduled Share",
        "provider": "smtp",
        "include_transcript": True,
        "include_summary": True,
        "include_minutes": True,
        "scheduled_at": schedule_time.isoformat()
    }
    res = client.post("/api/v1/emails/schedule", json=schedule_payload, headers=headers)
    assert res.status_code == 201
    scheduled_data = res.json()
    assert scheduled_data["status"] == "pending"
    assert scheduled_data["recipient"] == "scheduled_friend@example.com"
    assert scheduled_data["provider"] == "smtp"

    # 4. Test list scheduled emails
    res = client.get("/api/v1/emails/scheduled", headers=headers)
    assert res.status_code == 200
    scheduled_list = res.json()
    assert len(scheduled_list) == 1
    assert scheduled_list[0]["recipient"] == "scheduled_friend@example.com"
    email_id = scheduled_list[0]["id"]

    # 5. Process queue (make it due by updating scheduled_at to past)
    db_email = db.query(ScheduledEmail).filter(ScheduledEmail.id == email_id).first()
    db_email.scheduled_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()

    processed_count = await EmailService.process_due_emails(db)
    assert processed_count == 1
    
    # Reload and assert sent status
    db.refresh(db_email)
    assert db_email.status == "sent"
    assert db_email.sent_at is not None

    # 6. Test cancel schedule endpoint (create another one, then cancel)
    res = client.post("/api/v1/emails/schedule", json=schedule_payload, headers=headers)
    assert res.status_code == 201
    new_email_id = res.json()["id"]

    res = client.delete(f"/api/v1/emails/scheduled/{new_email_id}", headers=headers)
    assert res.status_code == 204

    # Verify deleted
    deleted_email = db.query(ScheduledEmail).filter(ScheduledEmail.id == new_email_id).first()
    assert deleted_email is None
