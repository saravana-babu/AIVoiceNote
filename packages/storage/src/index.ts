import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';

export interface KeyValueStorage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
  clear(): Promise<void>;
}

// Secure storage client with fallbacks for Web/Desktop
class SecureStorage implements KeyValueStorage {
  private isSecureAvailable: boolean | null = null;

  private async checkSecureAvailable(): Promise<boolean> {
    if (this.isSecureAvailable !== null) {
      return this.isSecureAvailable;
    }
    try {
      // SecureStore is only available on iOS/Android native
      const available = await SecureStore.isAvailableAsync();
      this.isSecureAvailable = available;
      return available;
    } catch {
      this.isSecureAvailable = false;
      return false;
    }
  }

  async getItem(key: string): Promise<string | null> {
    const isSecure = await this.checkSecureAvailable();
    if (isSecure) {
      try {
        return await SecureStore.getItemAsync(key);
      } catch (err) {
        console.error('Failed to get item from SecureStore, trying AsyncStorage fallback', err);
      }
    }
    return await AsyncStorage.getItem(key);
  }

  async setItem(key: string, value: string): Promise<void> {
    const isSecure = await this.checkSecureAvailable();
    if (isSecure) {
      try {
        await SecureStore.setItemAsync(key, value);
        return;
      } catch (err) {
        console.error('Failed to set item in SecureStore, trying AsyncStorage fallback', err);
      }
    }
    await AsyncStorage.setItem(key, value);
  }

  async removeItem(key: string): Promise<void> {
    const isSecure = await this.checkSecureAvailable();
    if (isSecure) {
      try {
        await SecureStore.deleteItemAsync(key);
        return;
      } catch (err) {
        console.error('Failed to remove item in SecureStore, trying AsyncStorage fallback', err);
      }
    }
    await AsyncStorage.removeItem(key);
  }

  async clear(): Promise<void> {
    // Clear AsyncStorage fallback
    await AsyncStorage.clear();
    // expo-secure-store doesn't support a "clear all" command,
    // so we rely on individual item deletions or AsyncStorage clear.
  }
}

export const appStorage: KeyValueStorage = new SecureStorage();
export default appStorage;
