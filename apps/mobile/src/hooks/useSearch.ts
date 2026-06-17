import { useQuery } from '@tanstack/react-query';
import { ApiClient, SearchType, SearchResult } from '@voicemind/api';
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

export function useSearchQuery(query: string, type: SearchType = 'hybrid') {
  const isOnline = useSyncStore((state) => state.isOnline);

  return useQuery({
    queryKey: ['search', query, type, isOnline],
    queryFn: async (): Promise<SearchResult[]> => {
      if (!query.trim()) {
        return [];
      }

      if (isOnline) {
        try {
          const client = getApiClient();
          return await client.searchNotes(query, type);
        } catch (err) {
          console.warn('Online search failed, falling back to offline search', err);
        }
      }

      // Offline search fallback: client-side regex/keyword matching from SQLite cache
      const localNotes = await repository.getNotes();
      const qLower = query.toLowerCase();
      const results: SearchResult[] = [];

      for (const note of localNotes) {
        let matched = false;
        let score = 0.0;

        // Check title
        if (note.title.toLowerCase().includes(qLower)) {
          matched = true;
          score += 1.0;
        }

        // Check transcription
        if (note.transcription && note.transcription.toLowerCase().includes(qLower)) {
          matched = true;
          score += 0.5;
        }

        // Check summary
        if (note.summary && note.summary.toLowerCase().includes(qLower)) {
          matched = true;
          score += 0.6;
        }

        // Check tags
        if (note.tags && note.tags.some((t) => t.toLowerCase().includes(qLower))) {
          matched = true;
          score += 0.8;
        }

        if (matched) {
          results.push({
            note,
            score,
            match_type: 'fts', // offline fallback is keyword matching
          });
        }
      }

      // Sort by score desc
      return results.sort((a, b) => b.score - a.score);
    },
    enabled: query.trim().length > 0,
  });
}
