import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiClient, KnowledgeCollection, KnowledgeSource, KnowledgeSearchResult, KnowledgeChatResponse } from '@voicemind/api';
import { useAuthStore } from '../store/authStore.js';
import { useSyncStore } from '../store/syncStore.js';

const API_URL = 'http://localhost:8000/api/v1';

function getApiClient(): ApiClient {
  const accessToken = useAuthStore.getState().accessToken || undefined;
  return new ApiClient({ baseUrl: API_URL, token: accessToken });
}

export function useKnowledgeCollectionsQuery() {
  const isOnline = useSyncStore((state) => state.isOnline);

  return useQuery({
    queryKey: ['knowledge-collections'],
    queryFn: async (): Promise<KnowledgeCollection[]> => {
      if (isOnline) {
        const client = getApiClient();
        return await client.getKnowledgeCollections();
      }
      return [];
    },
    enabled: isOnline,
  });
}

export function useCreateCollectionMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { name: string; description?: string }) => {
      const client = getApiClient();
      return await client.createKnowledgeCollection(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-collections'] });
    },
  });
}

export function useDeleteCollectionMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (collectionId: string) => {
      const client = getApiClient();
      await client.deleteKnowledgeCollection(collectionId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-collections'] });
    },
  });
}

export function useKnowledgeSourcesQuery(collectionId?: string) {
  const isOnline = useSyncStore((state) => state.isOnline);

  return useQuery({
    queryKey: ['knowledge-sources', collectionId],
    queryFn: async (): Promise<KnowledgeSource[]> => {
      if (isOnline) {
        const client = getApiClient();
        return await client.getKnowledgeSources(collectionId);
      }
      return [];
    },
    enabled: isOnline,
  });
}

export function useUploadSourceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      fileUri,
      filename,
      mimeType,
      collectionId,
    }: {
      fileUri: string;
      filename: string;
      mimeType: string;
      collectionId?: string;
    }) => {
      const client = getApiClient();
      return await client.uploadKnowledgeSource(fileUri, filename, mimeType, collectionId);
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-sources', variables.collectionId] });
    },
  });
}

export function useDeleteSourceMutation(collectionId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (sourceId: string) => {
      const client = getApiClient();
      await client.deleteKnowledgeSource(sourceId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-sources', collectionId] });
    },
  });
}

export function useSearchKnowledgeQuery(
  query: string,
  collectionId?: string,
  sourceId?: string,
) {
  const isOnline = useSyncStore((state) => state.isOnline);

  return useQuery({
    queryKey: ['knowledge-search', query, collectionId, sourceId],
    queryFn: async (): Promise<KnowledgeSearchResult[]> => {
      if (isOnline && query.trim().length > 0) {
        const client = getApiClient();
        return await client.searchKnowledge(query, collectionId, sourceId);
      }
      return [];
    },
    enabled: isOnline && query.trim().length > 0,
  });
}

export function useChatKnowledgeMutation() {
  return useMutation({
    mutationFn: async ({
      message,
      collectionId,
      sourceId,
      chatHistory,
      provider,
      model,
    }: {
      message: string;
      collectionId?: string;
      sourceId?: string;
      chatHistory?: Array<{ role: string; content: string }>;
      provider?: string;
      model?: string;
    }): Promise<KnowledgeChatResponse> => {
      const client = getApiClient();
      return await client.chatKnowledge(
        message,
        collectionId,
        sourceId,
        chatHistory,
        provider,
        model,
      );
    },
  });
}
