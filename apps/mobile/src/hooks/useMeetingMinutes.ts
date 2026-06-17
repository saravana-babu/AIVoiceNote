import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiClient, MeetingMinutes } from '@voicemind/api';
import { NoteRepository } from '../database/NoteRepository.js';
import { useAuthStore } from '../store/authStore.js';
import { useSyncStore } from '../store/syncStore.js';
import { config } from '../config.js';

const repository = NoteRepository.getInstance();
const API_URL = config.API_URL;

function getApiClient(): ApiClient {
  const accessToken = useAuthStore.getState().accessToken || undefined;
  return new ApiClient({ baseUrl: API_URL, token: accessToken });
}

export function useMeetingMinutesQuery(noteId: string) {
  const isOnline = useSyncStore((state) => state.isOnline);

  return useQuery({
    queryKey: ['meeting-minutes', noteId],
    queryFn: async (): Promise<MeetingMinutes | null> => {
      // 1. Try local SQLite/mock cache first
      const cached = await repository.getMeetingMinutes(noteId);
      if (cached) {
        return cached;
      }

      // 2. If online and not cached, fetch from server and update local cache
      if (isOnline) {
        try {
          const client = getApiClient();
          const serverMinutes = await client.getMeetingMinutes(noteId);
          await repository.saveMeetingMinutes(noteId, serverMinutes);
          return serverMinutes;
        } catch (err: any) {
          // If 404/NOT_FOUND, return null (meaning no minutes generated yet)
          if (err.message === 'NOT_FOUND') {
            return null;
          }
          throw err;
        }
      }

      return null;
    },
  });
}

export function useGenerateMinutesMutation() {
  const queryClient = useQueryClient();
  const isOnline = useSyncStore((state) => state.isOnline);

  return useMutation({
    mutationFn: async ({
      noteId,
      provider,
      model,
    }: {
      noteId: string;
      provider?: string;
      model?: string;
    }) => {
      if (!isOnline) {
        throw new Error('You must be online to generate meeting minutes.');
      }

      const client = getApiClient();
      const res = await client.generateMeetingMinutes(noteId, provider, model);

      // Save to SQLite/mock local cache
      await repository.saveMeetingMinutes(noteId, res.minutes);
      return res.minutes;
    },
    onSuccess: (data, variables) => {
      // Invalidate query to update details screen
      queryClient.invalidateQueries({ queryKey: ['meeting-minutes', variables.noteId] });
    },
  });
}

export function useDeleteMinutesMutation() {
  const queryClient = useQueryClient();
  const isOnline = useSyncStore((state) => state.isOnline);

  return useMutation({
    mutationFn: async (noteId: string) => {
      // Delete locally
      await repository.deleteMeetingMinutes(noteId);

      // Delete on server if online
      if (isOnline) {
        try {
          const client = getApiClient();
          await client.deleteMeetingMinutes(noteId);
        } catch (err) {
          console.warn('Failed to delete minutes on server', err);
        }
      }
    },
    onSuccess: (data, noteId) => {
      queryClient.invalidateQueries({ queryKey: ['meeting-minutes', noteId] });
    },
  });
}
