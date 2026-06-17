/* eslint-disable no-console */
import * as SQLite from 'expo-sqlite';
import { VoiceNote } from '@voicemind/shared';
import { MeetingMinutes } from '@voicemind/api';

let dbInstance: SQLite.SQLiteDatabase | null = null;
let isInMemoryMock = false;

interface MockNote extends Omit<VoiceNote, 'tags' | 'transcription' | 'summary'> {
  sync_status?: string;
}

// Simple in-memory JS mock database for Web/Desktop browser targets
export const mockDb = {
  notes: new Map<string, MockNote>(),
  recordings: new Map<
    string,
    { id: string; note_id: string; local_uri: string; is_uploaded: number }
  >(),
  transcripts: new Map<string, { note_id: string; text: string }>(),
  summaries: new Map<string, { note_id: string; text: string }>(),
  tags: [] as { note_id: string; tag: string }[],
  meeting_minutes: new Map<string, MeetingMinutes>(),
  sync_queue: [] as {
    id: number;
    action: 'CREATE' | 'UPDATE' | 'DELETE';
    table_name: string;
    record_id: string;
    payload: string | null;
    created_at: string;
  }[],
};

export async function getDbConnection(): Promise<SQLite.SQLiteDatabase | null> {
  if (dbInstance) return dbInstance;
  if (isInMemoryMock) return null;

  try {
    dbInstance = await SQLite.openDatabaseAsync('voicemind_app.db');
    return dbInstance;
  } catch (err) {
    console.warn('SQLite not available in this environment. Falling back to in-memory mock.', err);
    isInMemoryMock = true;
    return null;
  }
}

export async function initializeDatabase() {
  const db = await getDbConnection();
  if (!db) {
    console.log('In-memory database initialized for offline simulation.');
    return;
  }

  // Create tables in SQLite
  await db.execAsync(`
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS notes (
      id TEXT PRIMARY KEY NOT NULL,
      title TEXT NOT NULL,
      duration_sec INTEGER NOT NULL,
      file_path TEXT NOT NULL,
      status TEXT NOT NULL,
      sync_status TEXT DEFAULT 'pending',
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS recordings (
      id TEXT PRIMARY KEY NOT NULL,
      note_id TEXT NOT NULL,
      local_uri TEXT NOT NULL,
      is_uploaded INTEGER DEFAULT 0,
      FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS transcripts (
      note_id TEXT PRIMARY KEY NOT NULL,
      text TEXT NOT NULL,
      confidence REAL,
      FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS summaries (
      note_id TEXT PRIMARY KEY NOT NULL,
      text TEXT NOT NULL,
      FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS tags (
      note_id TEXT NOT NULL,
      tag TEXT NOT NULL,
      PRIMARY KEY(note_id, tag),
      FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS meeting_minutes (
      note_id TEXT PRIMARY KEY NOT NULL,
      overview TEXT NOT NULL,
      agenda TEXT NOT NULL,
      discussion_points TEXT NOT NULL,
      decisions TEXT NOT NULL,
      risks TEXT NOT NULL,
      action_items TEXT NOT NULL,
      provider TEXT NOT NULL,
      model TEXT NOT NULL,
      prompt_tokens INTEGER NOT NULL,
      completion_tokens INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY(note_id) REFERENCES notes(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS sync_queue (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      action TEXT NOT NULL,
      table_name TEXT NOT NULL,
      record_id TEXT NOT NULL,
      payload TEXT,
      created_at TEXT NOT NULL
    );
  `);
  console.log('SQLite database structures initialized successfully.');
}
