from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import json
from datetime import datetime

from app.database import get_db
from app.api.deps import get_current_user
from app.models.models import User, Note, ScheduledEmail
from app.schemas import schemas
from app.services.email_service import EmailService

router = APIRouter()

@router.post("/send-now", status_code=status.HTTP_200_OK)
async def send_email_now(
    payload: schemas.EmailSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    note = db.query(Note).filter(Note.id == payload.note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    # Render template
    html = EmailService.render_email_html(
        note=note,
        include_transcript=payload.include_transcript,
        include_summary=payload.include_summary,
        include_minutes=payload.include_minutes
    )

    # Attachments
    attachments = []
    if payload.include_summary and note.summaries:
        summary_text = ""
        for s in note.summaries:
            summary_text += f"=== {s.summary_type.upper()} ===\n"
            try:
                data = json.loads(s.structured_data)
                summary_text += json.dumps(data, indent=2)
            except Exception:
                summary_text += s.structured_data
            summary_text += "\n\n"
        attachments.append(("ai_summaries.txt", summary_text.encode("utf-8")))

    try:
        await EmailService.send_email(
            recipient=payload.recipient,
            subject=payload.subject,
            html_content=html,
            attachments=attachments,
            provider=payload.provider
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email: {str(e)}"
        )

    return {"status": "success", "message": "Email sent successfully."}

@router.post("/schedule", response_model=schemas.ScheduledEmailResponse, status_code=status.HTTP_201_CREATED)
async def schedule_email(
    payload: schemas.EmailScheduleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    note = db.query(Note).filter(Note.id == payload.note_id, Note.user_id == current_user.id).first()
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    # Determine email type label
    types = []
    if payload.include_transcript:
        types.append("transcript")
    if payload.include_summary:
        types.append("summary")
    if payload.include_minutes:
        types.append("minutes")
    email_type = "+".join(types) if types else "none"

    scheduled_email = ScheduledEmail(
        note_id=payload.note_id,
        user_id=current_user.id,
        recipient=payload.recipient,
        subject=payload.subject,
        email_type=email_type,
        provider=payload.provider,
        include_transcript=payload.include_transcript,
        include_summary=payload.include_summary,
        include_minutes=payload.include_minutes,
        scheduled_at=payload.scheduled_at,
        status="pending"
    )

    db.add(scheduled_email)
    db.commit()
    db.refresh(scheduled_email)
    return scheduled_email

@router.get("/scheduled", response_model=List[schemas.ScheduledEmailResponse])
async def list_scheduled_emails(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    emails = db.query(ScheduledEmail).filter(
        ScheduledEmail.user_id == current_user.id
    ).order_by(ScheduledEmail.scheduled_at.desc()).all()
    return emails

@router.delete("/scheduled/{email_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_scheduled_email(
    email_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    email = db.query(ScheduledEmail).filter(
        ScheduledEmail.id == email_id,
        ScheduledEmail.user_id == current_user.id
    ).first()
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scheduled email not found"
        )

    if email.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending scheduled emails can be cancelled."
        )

    db.delete(email)
    db.commit()
    return None
