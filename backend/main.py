from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

app = FastAPI(title="VoiceMind AI API", version="1.0.0")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VoiceNoteResponse(BaseModel):
    id: str
    title: str
    createdAt: str
    durationSec: float
    filePath: str
    status: str
    transcription: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = []

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/notes", response_model=List[VoiceNoteResponse])
def get_notes():
    # Mock voice notes matching the shared package TypeScript type
    return [
        {
            "id": "1",
            "title": "Project Foundation Brainstorm",
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "durationSec": 45.2,
            "filePath": "/audio/note_1.m4a",
            "status": "completed",
            "transcription": "This is a transcribed voice note about the Turborepo monorepo setup.",
            "summary": "Turborepo monorepo setup discussion.",
            "tags": ["foundation", "setup"]
        }
    ]

@app.post("/notes/upload", response_model=VoiceNoteResponse)
async def upload_audio(file: UploadFile = File(...)):
    # Mock audio upload processing
    note_id = str(uuid.uuid4())
    return {
        "id": note_id,
        "title": f"New Voice Note ({file.filename})",
        "createdAt": datetime.utcnow().isoformat() + "Z",
        "durationSec": 10.0,
        "filePath": f"/audio/{note_id}_{file.filename}",
        "status": "completed",
        "transcription": "Mock transcription for uploaded file.",
        "summary": "Mock summary for uploaded file.",
        "tags": ["uploaded"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
