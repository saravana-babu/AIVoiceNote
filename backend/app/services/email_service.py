import os
import json
import logging
import smtplib
import asyncio
import html
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import SessionLocal
from app.models.models import Note, Transcript, StructuredSummary, MeetingMinutes, ScheduledEmail

logger = logging.getLogger(__name__)

def html_escape(text: str) -> str:
    return html.escape(text)

def extract_text_from_json(data) -> str:
    if isinstance(data, str):
        return data
    elif isinstance(data, list):
        return " ".join(extract_text_from_json(item) for item in data if item is not None)
    elif isinstance(data, dict):
        return " ".join(extract_text_from_json(val) for val in data.values() if val is not None)
    return ""


class EmailService:
    @staticmethod
    def render_email_html(
        note: Note,
        include_transcript: bool,
        include_summary: bool,
        include_minutes: bool
    ) -> str:
        # Base template style
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    background-color: #121214;
                    color: #e1e1e6;
                    margin: 0;
                    padding: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    padding: 24px;
                    background-color: #1a1a1e;
                    border-radius: 16px;
                    border: 1px solid #29292e;
                }}
                .header {{
                    text-align: center;
                    border-bottom: 1px solid #29292e;
                    padding-bottom: 20px;
                    margin-bottom: 20px;
                }}
                .logo {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #9b59b6;
                    text-decoration: none;
                }}
                .note-meta {{
                    background-color: #29292e;
                    border-radius: 8px;
                    padding: 16px;
                    margin-bottom: 24px;
                }}
                .note-title {{
                    font-size: 18px;
                    font-weight: bold;
                    margin: 0 0 8px 0;
                    color: #ffffff;
                }}
                .meta-item {{
                    font-size: 12px;
                    color: #a8a8b3;
                    margin-right: 16px;
                }}
                .section {{
                    margin-bottom: 32px;
                }}
                .section-title {{
                    font-size: 16px;
                    font-weight: bold;
                    color: #9b59b6;
                    margin-bottom: 12px;
                    border-left: 4px solid #9b59b6;
                    padding-left: 8px;
                }}
                .card {{
                    background-color: #202024;
                    border: 1px solid #29292e;
                    border-radius: 8px;
                    padding: 16px;
                    margin-bottom: 12px;
                }}
                .card-title {{
                    font-size: 14px;
                    font-weight: bold;
                    color: #ffffff;
                    margin-top: 0;
                    margin-bottom: 8px;
                    text-transform: capitalize;
                }}
                p {{
                    font-size: 14px;
                    line-height: 1.6;
                    margin: 0 0 12px 0;
                    color: #c4c4cc;
                }}
                ul, ol {{
                    margin: 0;
                    padding-left: 20px;
                    color: #c4c4cc;
                    font-size: 14px;
                }}
                li {{
                    margin-bottom: 6px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 12px;
                }}
                th, td {{
                    border: 1px solid #29292e;
                    padding: 10px;
                    text-align: left;
                    font-size: 13px;
                }}
                th {{
                    background-color: #29292e;
                    color: #ffffff;
                }}
                .footer {{
                    text-align: center;
                    font-size: 12px;
                    color: #7c7c8a;
                    border-top: 1px solid #29292e;
                    padding-top: 20px;
                    margin-top: 30px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="logo">🌌 VoiceMind AI</div>
                </div>
                
                <div class="note-meta">
                    <h2 class="note-title">{html_escape(note.title)}</h2>
                    <span class="meta-item">⏱️ Duration: {note.duration_sec}s</span>
                    <span class="meta-item">📅 Date: {note.created_at.strftime('%Y-%m-%d %H:%M')}</span>
                </div>
        """

        # 1. Transcript Section
        if include_transcript and note.transcript:
            html += f"""
                <div class="section">
                    <div class="section-title">📝 Audio Transcript</div>
                    <div class="card">
                        <p>{html_escape(note.transcript.text)}</p>
                    </div>
                </div>
            """

        # 2. AI Summary Section
        if include_summary and note.summaries:
            html += """
                <div class="section">
                    <div class="section-title">🤖 AI Summaries</div>
            """
            for summary in note.summaries:
                try:
                    data = json.loads(summary.structured_data)
                except Exception:
                    data = {"summary": summary.structured_data}
                
                html += f"""
                    <div class="card">
                        <div class="card-title">{html_escape(summary.summary_type.replace('_', ' '))}</div>
                """
                
                # Render keys/values or lists nicely
                if isinstance(data, dict):
                    for k, v in data.items():
                        clean_key = k.replace('_', ' ').capitalize()
                        if isinstance(v, list):
                            html += f"<p><strong>{html_escape(clean_key)}:</strong></p><ul>"
                            for item in v:
                                html += f"<li>{html_escape(str(item))}</li>"
                            html += "</ul>"
                        else:
                            html += f"<p><strong>{html_escape(clean_key)}:</strong> {html_escape(str(v))}</p>"
                else:
                    html += f"<p>{html_escape(str(data))}</p>"
                
                html += "</div>"
            html += "</div>"

        # 3. Meeting Minutes Section
        if include_minutes and note.meeting_minutes:
            mm = note.meeting_minutes
            try:
                agenda = json.loads(mm.agenda)
            except Exception:
                agenda = []
            try:
                discussion = json.loads(mm.discussion_points)
            except Exception:
                discussion = []
            try:
                decisions = json.loads(mm.decisions)
            except Exception:
                decisions = []
            try:
                risks = json.loads(mm.risks)
            except Exception:
                risks = []
            try:
                action_items = json.loads(mm.action_items)
            except Exception:
                action_items = []

            html += f"""
                <div class="section">
                    <div class="section-title">⚡ Meeting Minutes</div>
                    <div class="card">
                        <div class="card-title">Overview</div>
                        <p>{html_escape(mm.overview)}</p>
                    </div>
            """

            if agenda:
                html += """
                    <div class="card">
                        <div class="card-title">Agenda</div>
                        <ol>
                """
                for item in agenda:
                    html += f"<li>{html_escape(str(item))}</li>"
                html += "</ol></div>"

            if discussion:
                html += """
                    <div class="card">
                        <div class="card-title">Discussion Points</div>
                """
                for item in discussion:
                    topic = item.get('topic', '')
                    summary = item.get('summary', '')
                    html += f"<p><strong>{html_escape(str(topic))}:</strong> {html_escape(str(summary))}</p>"
                html += "</div>"

            if decisions:
                html += """
                    <div class="card">
                        <div class="card-title">Key Decisions</div>
                        <ul>
                """
                for dec in decisions:
                    html += f"<li>{html_escape(str(dec))}</li>"
                html += "</ul></div>"

            if risks:
                html += """
                    <div class="card">
                        <div class="card-title">Identified Risks</div>
                        <ul>
                """
                for risk in risks:
                    html += f"<li>⚠️ {html_escape(str(risk))}</li>"
                html += "</ul></div>"

            if action_items:
                html += """
                    <div class="card">
                        <div class="card-title">Action Items & Owners</div>
                        <table>
                            <thead>
                                <tr>
                                    <th>Task</th>
                                    <th>Owner</th>
                                    <th>Due Date</th>
                                </tr>
                            </thead>
                            <tbody>
                """
                for item in action_items:
                    task = item.get('task', '')
                    owner = item.get('owner', '')
                    due = item.get('due_date', '')
                    html += f"""
                        <tr>
                            <td>{html_escape(str(task))}</td>
                            <td><strong>{html_escape(str(owner))}</strong></td>
                            <td>{html_escape(str(due))}</td>
                        </tr>
                    """
                html += """
                            </tbody>
                        </table>
                    </div>
                """
            html += "</div>"

        # End container
        html += """
                <div class="footer">
                    <p>Sent automatically by VoiceMind AI.<br>Pair programming with Antigravity AI.</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    @staticmethod
    async def send_email(
        recipient: str,
        subject: str,
        html_content: str,
        attachments: Optional[List[tuple[str, bytes]]] = None,
        provider: str = "smtp"
    ) -> None:
        logger.info(f"Dispatching email via provider: {provider}")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = recipient

        # Attach HTML body
        msg.attach(MIMEText(html_content, "html"))

        # Add attachments if any
        if attachments:
            for filename, data in attachments:
                part = MIMEApplication(data)
                part.add_header("Content-Disposition", "attachment", filename=filename)
                msg.attach(part)

        # Check SMTP settings. If user/password/host is missing, perform a mock delivery.
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning("SMTP credentials missing. Logging email and dumping to local filesystem.")
            # Dump to filesystem for local testing
            os.makedirs("sent_emails", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sent_emails/{timestamp}_{recipient}_{subject.replace(' ', '_')}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"Mock email successfully dumped to: {filename}")
            return

        # Synchronous SMTP dispatch in executor to prevent blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, EmailService._send_smtp_sync, msg, recipient)

    @staticmethod
    def _send_smtp_sync(msg: MIMEMultipart, recipient: str) -> None:
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, [recipient], msg.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, [recipient], msg.as_string())

    @staticmethod
    async def process_due_emails(db: Session) -> int:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        due_emails = db.query(ScheduledEmail).filter(
            ScheduledEmail.status == "pending",
            ScheduledEmail.scheduled_at <= now
        ).all()

        processed_count = 0
        for email in due_emails:
            try:
                # Load associated note and fetch properties
                note = db.query(Note).filter(Note.id == email.note_id).first()
                if not note:
                    raise ValueError(f"Note {email.note_id} not found.")

                # Render template
                html = EmailService.render_email_html(
                    note=note,
                    include_transcript=email.include_transcript,
                    include_summary=email.include_summary,
                    include_minutes=email.include_minutes
                )

                # Assemble simple text attachment if requested
                attachments = []
                if email.include_summary and note.summaries:
                    # Construct simple text summary file attachment
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

                # Dispatch
                await EmailService.send_email(
                    recipient=email.recipient,
                    subject=email.subject,
                    html_content=html,
                    attachments=attachments,
                    provider=email.provider
                )

                # Update status
                email.status = "sent"
                email.sent_at = datetime.now(timezone.utc)
                email.error_message = None
            except Exception as e:
                logger.exception(f"Scheduled email {email.id} dispatch failed.")
                email.status = "failed"
                email.error_message = str(e)
            
            db.commit()
            processed_count += 1

        return processed_count

async def start_scheduled_email_worker_loop():
    logger.info("Starting scheduled email background worker loop...")
    while True:
        db = None
        try:
            # Open direct session locally
            db = SessionLocal()
            count = await EmailService.process_due_emails(db)
            if count > 0:
                logger.info(f"Processed {count} due scheduled emails.")
        except Exception as e:
            from app.core.metrics import track_sync_failure
            track_sync_failure()
            logger.exception("Error in scheduled email worker loop.")
        finally:
            if db:
                db.close()
        
        # Poll every 15 seconds
        await asyncio.sleep(15)

