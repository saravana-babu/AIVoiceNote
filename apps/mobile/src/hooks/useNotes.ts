import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { NoteRepository } from '../database/NoteRepository.js';
import { useSyncStore } from '../store/syncStore.js';
import { VoiceNote } from '@voicemind/shared';

const repository = NoteRepository.getInstance();

export function useNotesQuery() {
  return useQuery({
    queryKey: ['notes'],
    queryFn: async () => {
      return await repository.getNotes();
    },
  });
}

export function useSaveNoteMutation() {
  const queryClient = useQueryClient();
  const syncPending = useSyncStore((state) => state.syncPendingNotes);

  return useMutation({
    mutationFn: async ({
      note,
      transcription,
      summary,
      tags,
    }: {
      note: Omit<VoiceNote, 'tags' | 'transcription' | 'summary'>;
      transcription?: string;
      summary?: string;
      tags?: string[];
    }) => {
      await repository.saveNote(note, transcription, summary, tags);
    },
    // Optimistic updates
    onMutate: async (variables) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['notes'] });

      // Snapshot the previous notes
      const previousNotes = queryClient.getQueryData<VoiceNote[]>(['notes']) || [];

      // Construct the optimistic note
      const optimisticNote: VoiceNote = {
        ...variables.note,
        transcription: variables.transcription,
        summary: variables.summary,
        tags: variables.tags || [],
        status: variables.note.status,
      };

      // Optimistically insert/update the query cache
      const exists = previousNotes.some((n) => n.id === variables.note.id);
      const newNotes = exists
        ? previousNotes.map((n) => (n.id === variables.note.id ? optimisticNote : n))
        : [optimisticNote, ...previousNotes];

      queryClient.setQueryData(['notes'], newNotes);

      return { previousNotes };
    },
    onError: (err, newTodo, context) => {
      // Rollback to previous state
      if (context?.previousNotes) {
        queryClient.setQueryData(['notes'], context.previousNotes);
      }
    },
    onSuccess: () => {
      // Invalidate queries to fetch clean records from SQLite
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      // Trigger background sync
      syncPending();
    },
  });
}

export function useDeleteNoteMutation() {
  const queryClient = useQueryClient();
  const syncPending = useSyncStore((state) => state.syncPendingNotes);

  return useMutation({
    mutationFn: async (id: string) => {
      await repository.deleteNote(id);
    },
    // Optimistic deletion
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['notes'] });

      const previousNotes = queryClient.getQueryData<VoiceNote[]>(['notes']) || [];

      // Filter out the deleted note from cache
      queryClient.setQueryData(
        ['notes'],
        previousNotes.filter((n) => n.id !== id),
      );

      return { previousNotes };
    },
    onError: (err, id, context) => {
      if (context?.previousNotes) {
        queryClient.setQueryData(['notes'], context.previousNotes);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      syncPending();
    },
  });
}
