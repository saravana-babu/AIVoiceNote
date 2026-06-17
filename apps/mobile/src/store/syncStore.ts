import { create } from 'zustand';
import { ApiClient } from '@voicemind/api';
import { NoteRepository } from '../database/NoteRepository.js';
import { useAuthStore } from './authStore.js';
import { appStorage } from '@voicemind/storage';
import { VoiceNote } from '@voicemind/shared';
import { config } from '../config.js';

export interface SyncState {
  isOnline: boolean;
  isSyncing: boolean;
  lastSyncTimestamp: string | null;
  setOnline: (online: boolean) => void;
  syncPendingNotes: () => Promise<void>;
  hydrate: () => Promise<void>;
  startScheduler: () => void;
  stopScheduler: () => void;
}

const API_URL = config.API_URL;
let syncIntervalId: ReturnType<typeof setInterval> | null = null;

export const useSyncStore = create<SyncState>((set, get) => ({
  isOnline: true,
  isSyncing: false,
  lastSyncTimestamp: null,

  setOnline: (online) => {
    const wasOffline = !get().isOnline;
    set({ isOnline: online });
    if (online && wasOffline) {
      console.warn('SyncStore: Connection restored. Triggering auto-sync...');
      get().syncPendingNotes();
    }
  },

  hydrate: async () => {
    try {
      const timestamp = await appStorage.getItem('last_sync_timestamp');
      set({ lastSyncTimestamp: timestamp });
    } catch (err) {
      console.error('SyncStore: Failed to hydrate last sync timestamp', err);
    }
  },

  syncPendingNotes: async () => {
    const { isSyncing, isOnline, lastSyncTimestamp } = get();
    if (isSyncing || !isOnline) return;

    const accessToken = useAuthStore.getState().accessToken;
    if (!accessToken) {
      return;
    }

    set({ isSyncing: true });
    const repository = NoteRepository.getInstance();

    try {
      const tasks = await repository.getPendingTasks();

      const clientChanges = tasks.map((t) => ({
        id: t.id,
        action: t.action,
        table_name: t.table_name,
        record_id: t.record_id,
        payload: t.payload,
        created_at: t.created_at,
      }));

      const apiClient = new ApiClient({ baseUrl: API_URL, token: accessToken });

      const response = await apiClient.synchronize({
        last_sync_timestamp: lastSyncTimestamp,
        client_changes: clientChanges,
      });

      const processedIds = new Set(response.processed_client_task_ids);
      for (const task of tasks) {
        if (processedIds.has(task.id)) {
          await repository.removePendingTask(task.id, task.record_id, 'synced');
        }
      }

      const remainingTasks = await repository.getPendingTasks();
      const pendingRecordIds = new Set(remainingTasks.map((t) => t.record_id));

      for (const delta of response.server_changes) {
        if (pendingRecordIds.has(delta.id)) {
          console.warn(
            `SyncStore: Conflict resolved. Client has newer pending offline change for Note ${delta.id}. Local wins.`,
          );
          continue;
        }

        const voiceNote: VoiceNote = {
          id: delta.id,
          title: delta.title,
          durationSec: delta.duration_sec,
          filePath: delta.file_path,
          status: delta.status as VoiceNote['status'],
          createdAt: delta.created_at,
          transcription: delta.transcription || undefined,
          summary: delta.summary || undefined,
          tags: delta.tags,
        };

        await repository.saveServerNote(voiceNote);
      }

      for (const deletedId of response.deleted_record_ids) {
        if (pendingRecordIds.has(deletedId)) {
          continue;
        }
        await repository.deleteServerNote(deletedId);
      }

      const newTimestamp = response.server_timestamp;
      await appStorage.setItem('last_sync_timestamp', newTimestamp);
      set({ lastSyncTimestamp: newTimestamp, isOnline: true });
    } catch (err) {
      console.warn('SyncStore: Sync failed (network unreachable or timeout).', err);
      set({ isOnline: false });
    } finally {
      set({ isSyncing: false });
    }
  },

  startScheduler: () => {
    if (syncIntervalId) clearInterval(syncIntervalId);

    get()
      .hydrate()
      .then(() => {
        get().syncPendingNotes();
      });

    syncIntervalId = setInterval(() => {
      get().syncPendingNotes();
    }, 30000);

    const checkConnectivity = async () => {
      try {
        const res = await fetch(`${API_URL.replace('/api/v1', '')}/health`, { method: 'GET' });
        if (res.ok) {
          get().setOnline(true);
        } else {
          set({ isOnline: false });
        }
      } catch {
        set({ isOnline: false });
      }
    };

    checkConnectivity();
  },

  stopScheduler: () => {
    if (syncIntervalId) {
      clearInterval(syncIntervalId);
      syncIntervalId = null;
    }
  },
}));
