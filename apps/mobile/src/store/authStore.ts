import { create } from 'zustand';
import { UserProfile } from '@voicemind/shared';
import { appStorage } from '@voicemind/storage';

export interface AuthState {
  user: UserProfile | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuth: (user: UserProfile, accessToken: string, refreshToken: string) => Promise<void>;
  clearAuth: () => Promise<void>;
  hydrate: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: true,

  setAuth: async (user, accessToken, refreshToken) => {
    // Save tokens securely
    await appStorage.setItem('access_token', accessToken);
    await appStorage.setItem('refresh_token', refreshToken);
    await appStorage.setItem('user_profile', JSON.stringify(user));

    set({
      user,
      accessToken,
      refreshToken,
      isAuthenticated: true,
      isLoading: false,
    });
  },

  clearAuth: async () => {
    // Delete stored tokens
    await appStorage.removeItem('access_token');
    await appStorage.removeItem('refresh_token');
    await appStorage.removeItem('user_profile');

    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  hydrate: async () => {
    set({ isLoading: true });
    try {
      const accessToken = await appStorage.getItem('access_token');
      const refreshToken = await appStorage.getItem('refresh_token');
      const userStr = await appStorage.getItem('user_profile');

      if (accessToken && refreshToken && userStr) {
        const user = JSON.parse(userStr) as UserProfile;
        set({
          user,
          accessToken,
          refreshToken,
          isAuthenticated: true,
        });
      } else {
        // Clear anything partial
        await get().clearAuth();
      }
    } catch (err) {
      console.error('Failed to hydrate auth state from storage', err);
      await get().clearAuth();
    } finally {
      set({ isLoading: false });
    }
  },
}));
