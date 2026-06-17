import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiClient, NoteEnhancement } from '@voicemind/api';
import { useAuthStore } from '../store/authStore.js';
import { useSyncStore } from '../store/syncStore.js';
import { config } from '../config.js';

const API_URL = config.API_URL;

function getApiClient(): ApiClient {
  const accessToken = useAuthStore.getState().accessToken || undefined;
  return new ApiClient({ baseUrl: API_URL, token: accessToken });
}

export function useNoteEnhancementsQuery(noteId: string) {
  const isOnline = useSyncStore((state) => state.isOnline);

  return useQuery({
    queryKey: ['note-enhancements', noteId],
    queryFn: async (): Promise<NoteEnhancement[]> => {
      if (isOnline) {
        try {
          const client = getApiClient();
          return await client.getNoteEnhancements(noteId);
        } catch (err) {
          console.error('Failed to fetch note enhancements', err);
          return [];
        }
      }
      return [];
    },
    enabled: !!noteId && isOnline,
  });
}

export function useGenerateEnhancementMutation() {
  const queryClient = useQueryClient();
  const isOnline = useSyncStore((state) => state.isOnline);

  return useMutation({
    mutationFn: async ({
      noteId,
      enhancementType,
      provider,
      model,
    }: {
      noteId: string;
      enhancementType: string;
      provider?: string;
      model?: string;
    }) => {
      if (!isOnline) {
        throw new Error('You must be online to generate note enhancements.');
      }

      const client = getApiClient();
      const res = await client.generateNoteEnhancement(noteId, enhancementType, provider, model);
      return res.enhancement;
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['note-enhancements', variables.noteId] });
    },
  });
}

export function useDeleteEnhancementMutation() {
  const queryClient = useQueryClient();
  const isOnline = useSyncStore((state) => state.isOnline);

  return useMutation({
    mutationFn: async ({
      noteId,
      enhancementId,
    }: {
      noteId: string;
      enhancementId: string;
    }) => {
      if (!isOnline) {
        throw new Error('You must be online to delete note enhancements.');
      }

      const client = getApiClient();
      await client.deleteNoteEnhancement(enhancementId);
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['note-enhancements', variables.noteId] });
    },
  });
}
