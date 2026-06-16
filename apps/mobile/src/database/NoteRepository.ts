import { getDbConnection, mockDb } from './dbSetup.js';
import { VoiceNote } from '@voicemind/shared';

export interface SyncTask {
  id: number;
  action: 'CREATE' | 'UPDATE' | 'DELETE';
  table_name: string;
  record_id: string;
  payload: string | null;
  created_at: string;
}

export class NoteRepository {
  private static instance: NoteRepository;

  private constructor() {}

  public static getInstance(): NoteRepository {
    if (!NoteRepository.instance) {
      NoteRepository.instance = new NoteRepository();
    }
    return NoteRepository.instance;
  }

  // --- QUERY ALL LOCAL NOTES ---
  async getNotes(): Promise<VoiceNote[]> {
    const db = await getDbConnection();
    if (!db) {
      // Return in-memory mock notes
      return Array.from(mockDb.notes.values()).map((note) => {
        const transcript = mockDb.transcripts.get(note.id)?.text;
        const summary = mockDb.summaries.get(note.id)?.text;
        const noteTags = mockDb.tags.filter((t) => t.note_id === note.id).map((t) => t.tag);
        const rest = { ...note };
        delete rest.sync_status;
        return {
          ...rest,
          transcription: transcript,
          summary,
          tags: noteTags,
        } as VoiceNote;
      });
    }

    // Load notes from SQLite
    const notesRaw = await db.getAllAsync<{
      id: string;
      title: string;
      duration_sec: number;
      file_path: string;
      status: string;
      sync_status: string;
      created_at: string;
    }>('SELECT * FROM notes ORDER BY created_at DESC');

    const notes: VoiceNote[] = [];

    for (const raw of notesRaw) {
      // Load transcript
      const transcriptRaw = await db.getFirstAsync<{ text: string }>(
        'SELECT text FROM transcripts WHERE note_id = ?',
        [raw.id],
      );
      // Load summary
      const summaryRaw = await db.getFirstAsync<{ text: string }>(
        'SELECT text FROM summaries WHERE note_id = ?',
        [raw.id],
      );
      // Load tags
      const tagsRaw = await db.getAllAsync<{ tag: string }>(
        'SELECT tag FROM tags WHERE note_id = ?',
        [raw.id],
      );

      notes.push({
        id: raw.id,
        title: raw.title,
        durationSec: raw.duration_sec,
        filePath: raw.file_path,
        status: raw.status as VoiceNote['status'],
        createdAt: raw.created_at,
        transcription: transcriptRaw?.text,
        summary: summaryRaw?.text,
        tags: tagsRaw.map((t) => t.tag),
      });
    }

    return notes;
  }

  // --- SAVE / UPDATE NOTE ---
  async saveNote(
    note: Omit<VoiceNote, 'tags' | 'transcription' | 'summary'>,
    transcription?: string,
    summary?: string,
    tags: string[] = [],
  ): Promise<void> {
    const db = await getDbConnection();
    const nowStr = new Date().toISOString();

    if (!db) {
      // Save in mock
      const isCreate = !mockDb.notes.has(note.id);
      mockDb.notes.set(note.id, {
        id: note.id,
        title: note.title,
        durationSec: note.durationSec,
        filePath: note.filePath,
        status: note.status,
        createdAt: note.createdAt || nowStr,
        sync_status: 'pending',
      });

      if (transcription) {
        mockDb.transcripts.set(note.id, { note_id: note.id, text: transcription });
      }
      if (summary) {
        mockDb.summaries.set(note.id, { note_id: note.id, text: summary });
      }
      // Remove old tags
      mockDb.tags = mockDb.tags.filter((t) => t.note_id !== note.id);
      tags.forEach((tag) => {
        mockDb.tags.push({ note_id: note.id, tag });
      });

      // Queue sync action
      mockDb.sync_queue.push({
        id: Date.now() + Math.random(),
        action: isCreate ? 'CREATE' : 'UPDATE',
        table_name: 'notes',
        record_id: note.id,
        payload: JSON.stringify({
          id: note.id,
          title: note.title,
          durationSec: note.durationSec,
          filePath: note.filePath,
          status: note.status,
          transcription,
          summary,
          tags,
        }),
        created_at: nowStr,
      });

      return;
    }

    // Save in SQLite
    const existing = await db.getFirstAsync('SELECT id FROM notes WHERE id = ?', [note.id]);
    const action = existing ? 'UPDATE' : 'CREATE';

    if (action === 'CREATE') {
      await db.runAsync(
        'INSERT INTO notes (id, title, duration_sec, file_path, status, sync_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
        [note.id, note.title, note.durationSec, note.filePath, note.status, 'pending', nowStr],
      );
    } else {
      await db.runAsync(
        'UPDATE notes SET title = ?, duration_sec = ?, file_path = ?, status = ?, sync_status = ? WHERE id = ?',
        [note.title, note.durationSec, note.filePath, note.status, 'pending', note.id],
      );
    }

    // Save Transcript
    if (transcription) {
      await db.runAsync('INSERT OR REPLACE INTO transcripts (note_id, text) VALUES (?, ?)', [
        note.id,
        transcription,
      ]);
    }

    // Save Summary
    if (summary) {
      await db.runAsync('INSERT OR REPLACE INTO summaries (note_id, text) VALUES (?, ?)', [
        note.id,
        summary,
      ]);
    }

    // Save Tags
    await db.runAsync('DELETE FROM tags WHERE note_id = ?', [note.id]);
    for (const tag of tags) {
      await db.runAsync('INSERT INTO tags (note_id, tag) VALUES (?, ?)', [note.id, tag]);
    }

    // Queue in Sync Queue
    const payload = JSON.stringify({
      id: note.id,
      title: note.title,
      durationSec: note.durationSec,
      filePath: note.filePath,
      status: note.status,
      transcription,
      summary,
      tags,
    });

    await db.runAsync(
      'INSERT INTO sync_queue (action, table_name, record_id, payload, created_at) VALUES (?, ?, ?, ?, ?)',
      [action, 'notes', note.id, payload, nowStr],
    );
  }

  // --- DELETE NOTE ---
  async deleteNote(id: string): Promise<void> {
    const db = await getDbConnection();
    const nowStr = new Date().toISOString();

    if (!db) {
      // Mock delete
      mockDb.notes.delete(id);
      mockDb.transcripts.delete(id);
      mockDb.summaries.delete(id);
      mockDb.tags = mockDb.tags.filter((t) => t.note_id !== id);

      mockDb.sync_queue.push({
        id: Date.now() + Math.random(),
        action: 'DELETE',
        table_name: 'notes',
        record_id: id,
        payload: null,
        created_at: nowStr,
      });
      return;
    }

    // SQLite delete
    await db.runAsync('DELETE FROM notes WHERE id = ?', [id]);
    // Cascade constraints automatically handles deletes on foreign keys

    await db.runAsync(
      'INSERT INTO sync_queue (action, table_name, record_id, payload, created_at) VALUES (?, ?, ?, ?, ?)',
      ['DELETE', 'notes', id, null, nowStr],
    );
  }

  // --- SYNC QUEUE FETCH & FLUSH ---
  async getPendingTasks(): Promise<SyncTask[]> {
    const db = await getDbConnection();
    if (!db) {
      return mockDb.sync_queue;
    }
    return await db.getAllAsync<SyncTask>('SELECT * FROM sync_queue ORDER BY id ASC');
  }

  async removePendingTask(
    taskId: number,
    recordId: string,
    syncStatus: 'synced' | 'pending' = 'synced',
  ): Promise<void> {
    const db = await getDbConnection();
    if (!db) {
      mockDb.sync_queue = mockDb.sync_queue.filter((t) => t.id !== taskId);
      const note = mockDb.notes.get(recordId);
      if (note) {
        note.sync_status = syncStatus;
      }
      return;
    }

    // Delete task
    await db.runAsync('DELETE FROM sync_queue WHERE id = ?', [taskId]);

    // Update note status
    await db.runAsync('UPDATE notes SET sync_status = ? WHERE id = ?', [syncStatus, recordId]);
  }
}
