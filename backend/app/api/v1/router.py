from fastapi import APIRouter
from app.api.v1.endpoints import auth, workspaces, notes, recordings, transcripts, summaries, storage, sync, meeting_minutes, search, emails, enhancements, knowledge

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(notes.router, prefix="/notes", tags=["notes"])
api_router.include_router(recordings.router, prefix="/recordings", tags=["recordings"])
api_router.include_router(transcripts.router, prefix="/transcripts", tags=["transcripts"])
api_router.include_router(summaries.router, prefix="/summaries", tags=["summaries"])
api_router.include_router(storage.router, prefix="/storage", tags=["storage"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(meeting_minutes.router, prefix="/meeting-minutes", tags=["meeting-minutes"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(emails.router, prefix="/emails", tags=["emails"])
api_router.include_router(enhancements.router, prefix="/enhancements", tags=["enhancements"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])


