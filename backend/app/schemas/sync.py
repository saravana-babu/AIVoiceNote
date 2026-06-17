from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ClientSyncChange(BaseModel):
    id: int  # local queue task ID
    action: str  # "CREATE", "UPDATE", "DELETE"
    table_name: str  # "notes"
    record_id: str
    payload: Optional[str] = None
    created_at: datetime

class SyncRequest(BaseModel):
    last_sync_timestamp: Optional[datetime] = None
    client_changes: List[ClientSyncChange] = []

class ServerNoteDelta(BaseModel):
    id: str
    title: str
    duration_sec: int
    file_path: str
    status: str
    workspace_id: Optional[str] = None
    user_id: str
    created_at: datetime
    updated_at: datetime
    transcription: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = []

class SyncResponse(BaseModel):
    server_changes: List[ServerNoteDelta]
    deleted_record_ids: List[str]
    server_timestamp: datetime
    processed_client_task_ids: List[int]
