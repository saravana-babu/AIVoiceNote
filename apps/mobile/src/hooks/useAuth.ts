import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../store/authStore.js';
import { UserProfile } from '@voicemind/shared';

const API_URL = 'http://localhost:8000'; // Default API Host

interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserProfile;
}

export function useLoginMutation() {
  const setAuth = useAuthStore((state) => state.setAuth);

  return useMutation({
    mutationFn: async ({ email, password }) => {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Login failed');
      }
      return (await res.json()) as AuthResponse;
    },
    onSuccess: (data) => {
      setAuth(data.user, data.access_token, data.refresh_token);
    },
  });
}

export function useRegisterMutation() {
  const setAuth = useAuthStore((state) => state.setAuth);

  return useMutation({
    mutationFn: async ({ email, password, displayName }) => {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, display_name: displayName }),
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Registration failed');
      }
      return (await res.json()) as AuthResponse;
    },
    onSuccess: (data) => {
      setAuth(data.user, data.access_token, data.refresh_token);
    },
  });
}

export function useGoogleLoginMutation() {
  const setAuth = useAuthStore((state) => state.setAuth);

  return useMutation({
    mutationFn: async ({ email }) => {
      // Send mock token payload based on user email
      const token = `mock-google-${email}`;
      const res = await fetch(`${API_URL}/auth/oauth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, display_name: email.split('@')[0] }),
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Google sign-in failed');
      }
      return (await res.json()) as AuthResponse;
    },
    onSuccess: (data) => {
      setAuth(data.user, data.access_token, data.refresh_token);
    },
  });
}

export function useAppleLoginMutation() {
  const setAuth = useAuthStore((state) => state.setAuth);

  return useMutation({
    mutationFn: async ({ email }) => {
      const token = `mock-apple-${email}`;
      const res = await fetch(`${API_URL}/auth/oauth/apple`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, display_name: email.split('@')[0] }),
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Apple sign-in failed');
      }
      return (await res.json()) as AuthResponse;
    },
    onSuccess: (data) => {
      setAuth(data.user, data.access_token, data.refresh_token);
    },
  });
}

export function useLogoutMutation() {
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const refreshToken = useAuthStore((state) => state.refreshToken);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      if (!refreshToken) return;

      // Notify backend to revoke refresh token
      await fetch(`${API_URL}/auth/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => {
        // Fail silently and clear client state anyway
      });
    },
    onSettled: () => {
      clearAuth();
      queryClient.clear();
    },
  });
}

export function useResetPasswordRequestMutation() {
  return useMutation({
    mutationFn: async (email: string) => {
      const res = await fetch(`${API_URL}/auth/password-reset/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (!res.ok) throw new Error('Reset request failed');
      return await res.json();
    },
  });
}

export function useResetPasswordConfirmMutation() {
  return useMutation({
    mutationFn: async ({ token, newPassword }) => {
      const res = await fetch(`${API_URL}/auth/password-reset/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Password reset failed');
      }
      return await res.json();
    },
  });
}
