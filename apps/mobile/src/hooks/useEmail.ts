import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ApiClient,
  EmailSendRequest,
  EmailScheduleRequest,
  ScheduledEmailResponse,
} from '@voicemind/api';
import { useAuthStore } from '../store/authStore.js';
import { useSyncStore } from '../store/syncStore.js';

const API_URL = 'http://localhost:8000/api/v1';

function getApiClient(): ApiClient {
  const accessToken = useAuthStore.getState().accessToken || undefined;
  return new ApiClient({ baseUrl: API_URL, token: accessToken });
}

export function useScheduledEmailsQuery() {
  const isOnline = useSyncStore((state) => state.isOnline);

  return useQuery({
    queryKey: ['scheduled-emails', isOnline],
    queryFn: async (): Promise<ScheduledEmailResponse[]> => {
      if (!isOnline) {
        return [];
      }
      const client = getApiClient();
      return await client.getScheduledEmails();
    },
    enabled: isOnline,
  });
}

export function useSendEmailNowMutation() {
  const isOnline = useSyncStore((state) => state.isOnline);

  return useMutation({
    mutationFn: async (payload: EmailSendRequest) => {
      if (!isOnline) {
        throw new Error('You must be online to send emails.');
      }
      const client = getApiClient();
      await client.sendEmailNow(payload);
    },
  });
}

export function useScheduleEmailMutation() {
  const queryClient = useQueryClient();
  const isOnline = useSyncStore((state) => state.isOnline);

  return useMutation({
    mutationFn: async (payload: EmailScheduleRequest) => {
      if (!isOnline) {
        throw new Error('You must be online to schedule emails.');
      }
      const client = getApiClient();
      return await client.scheduleEmail(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-emails'] });
    },
  });
}

export function useCancelScheduledEmailMutation() {
  const queryClient = useQueryClient();
  const isOnline = useSyncStore((state) => state.isOnline);

  return useMutation({
    mutationFn: async (emailId: string) => {
      if (!isOnline) {
        throw new Error('You must be online to cancel scheduled emails.');
      }
      const client = getApiClient();
      await client.cancelScheduledEmail(emailId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduled-emails'] });
    },
  });
}
