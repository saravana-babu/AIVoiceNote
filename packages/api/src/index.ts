import { VoiceNote } from '@voicemind/shared';

export interface ApiClientConfig {
  baseUrl: string;
  token?: string;
}

export interface PresignUploadResponse {
  url: string;
  key: string;
}

export interface PresignDownloadResponse {
  url: string;
}

export interface MultipartInitiateResponse {
  upload_id: string;
  key: string;
}

export interface MultipartPartPresignedUrl {
  part_number: number;
  url: string;
}

export interface MultipartPresignPartsResponse {
  parts: MultipartPartPresignedUrl[];
}

export interface MultipartPartInfo {
  part_number: number;
  etag: string;
}

export interface MultipartCompleteResponse {
  location: string;
  key: string;
}

export class ApiClient {
  private config: ApiClientConfig;

  constructor(config: ApiClientConfig) {
    this.config = config;
  }

  setToken(token: string) {
    this.config.token = token;
  }

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (this.config.token) {
      headers['Authorization'] = `Bearer ${this.config.token}`;
    }
    return headers;
  }

  async checkHealth(): Promise<{ status: string }> {
    const res = await fetch(`${this.config.baseUrl}/health`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('API Health Check failed');
    return res.json();
  }

  async getNotes(): Promise<VoiceNote[]> {
    const res = await fetch(`${this.config.baseUrl}/notes`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch voice notes');
    return res.json();
  }

  async uploadAudio(fileUri: string): Promise<VoiceNote> {
    const formData = new FormData();
    formData.append('file', {
      uri: fileUri,
      name: 'recording.m4a',
      type: 'audio/m4a',
    } as unknown as Blob);

    const res = await fetch(`${this.config.baseUrl}/notes/upload`, {
      method: 'POST',
      headers: {
        ...(this.config.token ? { Authorization: `Bearer ${this.config.token}` } : {}),
      },
      body: formData,
    });

    if (!res.ok) throw new Error('Audio upload failed');
    return res.json();
  }

  // --- CLOUDFLARE R2 STORAGE ENDPOINTS ---
  async getPresignedUploadUrl(
    purpose: 'audio' | 'export',
    extension: string,
  ): Promise<PresignUploadResponse> {
    const cleanExt = extension.replace(/^\./, '');
    const res = await fetch(
      `${this.config.baseUrl}/storage/presign-upload?purpose=${purpose}&extension=${cleanExt}`,
      { headers: this.getHeaders() },
    );
    if (!res.ok) throw new Error('Failed to get presigned upload URL');
    return res.json();
  }

  async getPresignedDownloadUrl(key: string): Promise<PresignDownloadResponse> {
    const res = await fetch(
      `${this.config.baseUrl}/storage/presign-download?key=${encodeURIComponent(key)}`,
      { headers: this.getHeaders() },
    );
    if (!res.ok) throw new Error('Failed to get presigned download URL');
    return res.json();
  }

  async initiateMultipartUpload(
    purpose: 'audio' | 'export',
    extension: string,
  ): Promise<MultipartInitiateResponse> {
    const cleanExt = extension.replace(/^\./, '');
    const res = await fetch(`${this.config.baseUrl}/storage/multipart/initiate`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ purpose, extension: cleanExt }),
    });
    if (!res.ok) throw new Error('Failed to initiate multipart upload');
    return res.json();
  }

  async getMultipartPresignedParts(
    key: string,
    uploadId: string,
    partNumbers: number[],
  ): Promise<MultipartPresignPartsResponse> {
    const res = await fetch(`${this.config.baseUrl}/storage/multipart/presign-parts`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ key, upload_id: uploadId, part_numbers: partNumbers }),
    });
    if (!res.ok) throw new Error('Failed to generate presigned part URLs');
    return res.json();
  }

  async completeMultipartUpload(
    key: string,
    uploadId: string,
    parts: MultipartPartInfo[],
  ): Promise<MultipartCompleteResponse> {
    const res = await fetch(`${this.config.baseUrl}/storage/multipart/complete`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ key, upload_id: uploadId, parts }),
    });
    if (!res.ok) throw new Error('Failed to complete multipart upload');
    return res.json();
  }

  async abortMultipartUpload(key: string, uploadId: string): Promise<{ status: string }> {
    const res = await fetch(`${this.config.baseUrl}/storage/multipart/abort`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ key, upload_id: uploadId }),
    });
    if (!res.ok) throw new Error('Failed to abort multipart upload');
    return res.json();
  }

  // --- DELTA SYNCHRONIZATION ENDPOINT ---
  async synchronize(syncReq: SyncRequest): Promise<SyncResponse> {
    const res = await fetch(`${this.config.baseUrl}/sync/`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(syncReq),
    });
    if (!res.ok) throw new Error('Synchronization request failed');
    return res.json();
  }

  // --- MEETING MINUTES ENDPOINTS ---
  async getMeetingMinutes(noteId: string): Promise<MeetingMinutes> {
    const res = await fetch(`${this.config.baseUrl}/meeting-minutes/note/${noteId}`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      if (res.status === 404) {
        throw new Error('NOT_FOUND');
      }
      throw new Error('Failed to fetch meeting minutes');
    }
    return res.json();
  }

  async generateMeetingMinutes(
    noteId: string,
    provider?: string,
    model?: string,
  ): Promise<MeetingMinutesGenerateResponse> {
    const res = await fetch(`${this.config.baseUrl}/meeting-minutes/generate`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ note_id: noteId, provider, model }),
    });
    if (!res.ok) throw new Error('Failed to generate meeting minutes');
    return res.json();
  }

  async deleteMeetingMinutes(noteId: string): Promise<void> {
    const res = await fetch(`${this.config.baseUrl}/meeting-minutes/note/${noteId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete meeting minutes');
  }

  async searchNotes(
    query: string,
    type: SearchType = 'hybrid',
    limit: number = 20,
  ): Promise<SearchResult[]> {
    const params = new URLSearchParams({ q: query, type, limit: limit.toString() });
    const res = await fetch(`${this.config.baseUrl}/search?${params.toString()}`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Search failed');
    return res.json();
  }

  async sendEmailNow(payload: EmailSendRequest): Promise<void> {
    const res = await fetch(`${this.config.baseUrl}/emails/send-now`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to send email');
  }

  async scheduleEmail(payload: EmailScheduleRequest): Promise<ScheduledEmailResponse> {
    const res = await fetch(`${this.config.baseUrl}/emails/schedule`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to schedule email');
    return res.json();
  }

  async getScheduledEmails(): Promise<ScheduledEmailResponse[]> {
    const res = await fetch(`${this.config.baseUrl}/emails/scheduled`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch scheduled emails');
    return res.json();
  }

  async cancelScheduledEmail(emailId: string): Promise<void> {
    const res = await fetch(`${this.config.baseUrl}/emails/scheduled/${emailId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Failed to cancel scheduled email');
  }

  // --- NOTE ENHANCEMENT ENDPOINTS ---
  async getNoteEnhancements(noteId: string): Promise<NoteEnhancement[]> {
    const res = await fetch(`${this.config.baseUrl}/enhancements/note/${noteId}`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch note enhancements');
    return res.json();
  }

  async generateNoteEnhancement(
    noteId: string,
    enhancementType: string,
    provider?: string,
    model?: string,
  ): Promise<NoteEnhancementGenerateResponse> {
    const res = await fetch(`${this.config.baseUrl}/enhancements/generate`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        note_id: noteId,
        enhancement_type: enhancementType,
        provider,
        model,
      }),
    });
    if (!res.ok) throw new Error('Failed to generate note enhancement');
    return res.json();
  }

  async deleteNoteEnhancement(enhancementId: string): Promise<void> {
    const res = await fetch(`${this.config.baseUrl}/enhancements/${enhancementId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete note enhancement');
  }

  // --- KNOWLEDGE ENGINE ENDPOINTS ---
  async getKnowledgeCollections(): Promise<KnowledgeCollection[]> {
    const res = await fetch(`${this.config.baseUrl}/knowledge/collections`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch knowledge collections');
    return res.json();
  }

  async createKnowledgeCollection(payload: KnowledgeCollectionCreate): Promise<KnowledgeCollection> {
    const res = await fetch(`${this.config.baseUrl}/knowledge/collections`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Failed to create custom collection');
    return res.json();
  }

  async deleteKnowledgeCollection(collectionId: string): Promise<void> {
    const res = await fetch(`${this.config.baseUrl}/knowledge/collections/${collectionId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete custom collection');
  }

  async getKnowledgeSources(collectionId?: string): Promise<KnowledgeSource[]> {
    const url = collectionId
      ? `${this.config.baseUrl}/knowledge/sources?collection_id=${collectionId}`
      : `${this.config.baseUrl}/knowledge/sources`;
    const res = await fetch(url, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch knowledge sources');
    return res.json();
  }

  async uploadKnowledgeSource(fileUri: string, filename: string, mimeType: string, collectionId?: string): Promise<KnowledgeSource> {
    const formData = new FormData();
    formData.append('file', {
      uri: fileUri,
      name: filename,
      type: mimeType,
    } as unknown as Blob);
    
    if (collectionId) {
      formData.append('collection_id', collectionId);
    }

    const res = await fetch(`${this.config.baseUrl}/knowledge/sources/upload`, {
      method: 'POST',
      headers: {
        ...(this.config.token ? { Authorization: `Bearer ${this.config.token}` } : {}),
      },
      body: formData,
    });
    if (!res.ok) throw new Error('Failed to upload document source');
    return res.json();
  }

  async deleteKnowledgeSource(sourceId: string): Promise<void> {
    const res = await fetch(`${this.config.baseUrl}/knowledge/sources/${sourceId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete knowledge source');
  }

  async searchKnowledge(query: string, collectionId?: string, sourceId?: string, limit: number = 20): Promise<KnowledgeSearchResult[]> {
    const res = await fetch(`${this.config.baseUrl}/knowledge/search`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ query, collection_id: collectionId, source_id: sourceId, limit }),
    });
    if (!res.ok) throw new Error('Knowledge search failed');
    return res.json();
  }

  async chatKnowledge(
    message: string,
    collectionId?: string,
    sourceId?: string,
    chatHistory?: Array<{ role: string; content: string }>,
    provider?: string,
    model?: string,
  ): Promise<KnowledgeChatResponse> {
    const res = await fetch(`${this.config.baseUrl}/knowledge/chat`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        message,
        collection_id: collectionId,
        source_id: sourceId,
        chat_history: chatHistory,
        provider,
        model,
      }),
    });
    if (!res.ok) throw new Error('Knowledge chat failed');
    return res.json();
  }
}

export interface ClientSyncChange {
  id: number;
  action: 'CREATE' | 'UPDATE' | 'DELETE';
  table_name: string;
  record_id: string;
  payload: string | null;
  created_at: string;
}

export interface SyncRequest {
  last_sync_timestamp: string | null;
  client_changes: ClientSyncChange[];
}

export interface ServerNoteDelta {
  id: string;
  title: string;
  duration_sec: number;
  file_path: string;
  status: string;
  workspace_id: string | null;
  user_id: string;
  created_at: string;
  updated_at: string;
  transcription: string | null;
  summary: string | null;
  tags: string[];
}

export interface SyncResponse {
  server_changes: ServerNoteDelta[];
  deleted_record_ids: string[];
  server_timestamp: string;
  processed_client_task_ids: number[];
}

export interface DiscussionPoint {
  topic: string;
  summary: string;
}

export interface ActionItem {
  task: string;
  owner: string;
  due_date: string;
}

export interface MeetingMinutes {
  note_id: string;
  overview: string;
  agenda: string[];
  discussion_points: DiscussionPoint[];
  decisions: string[];
  risks: string[];
  action_items: ActionItem[];
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  created_at: string;
  updated_at: string;
}

export interface MeetingMinutesGenerateResponse {
  minutes: MeetingMinutes;
  generation_time_ms: number;
}

export type SearchType = 'semantic' | 'fts' | 'hybrid';

export interface SearchResult {
  note: VoiceNote;
  score: number;
  match_type: string;
}

export interface EmailSendRequest {
  note_id: string;
  recipient: string;
  subject: string;
  provider: 'smtp' | 'gmail';
  include_transcript: boolean;
  include_summary: boolean;
  include_minutes: boolean;
}

export interface EmailScheduleRequest {
  note_id: string;
  recipient: string;
  subject: string;
  provider: 'smtp' | 'gmail';
  include_transcript: boolean;
  include_summary: boolean;
  include_minutes: boolean;
  scheduled_at: string; // ISO DateTime string
}

export interface ScheduledEmailResponse {
  id: string;
  note_id: string;
  user_id: string;
  recipient: string;
  subject: string;
  email_type: string;
  include_transcript: boolean;
  include_summary: boolean;
  include_minutes: boolean;
  status: 'pending' | 'sent' | 'failed';
  scheduled_at: string;
  sent_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface NoteEnhancement {
  id: string;
  note_id: string;
  enhancement_type: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  structured_data: any;
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  created_at: string;
  updated_at: string;
}

export interface NoteEnhancementGenerateResponse {
  enhancement: NoteEnhancement;
  generation_time_ms: number;
}

export interface KnowledgeCollection {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeCollectionCreate {
  name: string;
  description?: string;
}

export interface KnowledgeSource {
  id: string;
  title: string;
  source_type: string;
  file_path?: string;
  note_id?: string;
  collection_id?: string;
  created_at: string;
  updated_at: string;
  raw_content?: string;
}

export interface KnowledgeSearchResult {
  chunk_id: string;
  source_id: string;
  source_title: string;
  source_type: string;
  content: string;
  score: number;
}

export interface KnowledgeChatCitation {
  id: string;
  index: number;
  title: string;
  source_type: string;
  note_id?: string;
}

export interface KnowledgeChatResponse {
  response: string;
  citations: KnowledgeChatCitation[];
  suggested_questions: string[];
  provider: string;
  model: string;
}


