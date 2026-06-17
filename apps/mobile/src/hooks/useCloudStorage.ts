import { useState, useCallback } from 'react';
import * as FileSystem from 'expo-file-system';
import { ApiClient } from '@voicemind/api';
import { CloudStorageService } from '@voicemind/storage';
import { useAuthStore } from '../store/authStore.js';

const MULTIPART_THRESHOLD = 5 * 1024 * 1024; // 5MB threshold for multipart upload

export function useCloudUpload() {
  const [progress, setProgress] = useState<number>(0);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadedKey, setUploadedKey] = useState<string | null>(null);

  const accessToken = useAuthStore((state) => state.accessToken);

  const uploadFile = useCallback(
    async (
      localUri: string,
      purpose: 'audio' | 'export',
      extension: string,
      forceMultipart = false,
    ): Promise<string> => {
      setIsUploading(true);
      setProgress(0);
      setError(null);
      setUploadedKey(null);

      try {
        if (!accessToken) {
          throw new Error('User is not authenticated');
        }

        const apiClient = new ApiClient({
          baseUrl: 'http://localhost:8000/api/v1',
          token: accessToken,
        });
        const storageService = new CloudStorageService({ apiClient });

        const fileInfo = await FileSystem.getInfoAsync(localUri);
        if (!fileInfo.exists) {
          throw new Error('Local file not found');
        }

        let key = '';
        if (forceMultipart || fileInfo.size > MULTIPART_THRESHOLD) {
          key = await storageService.uploadMultipartFile(localUri, purpose, extension, (p) =>
            setProgress(p),
          );
        } else {
          key = await storageService.uploadSingleFile(localUri, purpose, extension, (p) =>
            setProgress(p),
          );
        }

        setUploadedKey(key);
        setProgress(100);
        return key;
      } catch (err: unknown) {
        const errMsg = err instanceof Error ? err.message : 'Cloud upload failed';
        setError(errMsg);
        throw err;
      } finally {
        setIsUploading(false);
      }
    },
    [accessToken],
  );

  return {
    uploadFile,
    progress,
    isUploading,
    error,
    uploadedKey,
  };
}

export function useCloudDownload() {
  const [progress, setProgress] = useState<number>(0);
  const [isDownloading, setIsDownloading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const accessToken = useAuthStore((state) => state.accessToken);

  const downloadFile = useCallback(
    async (key: string, localUri: string): Promise<void> => {
      setIsDownloading(true);
      setProgress(0);
      setError(null);

      try {
        if (!accessToken) {
          throw new Error('User is not authenticated');
        }

        const apiClient = new ApiClient({
          baseUrl: 'http://localhost:8000/api/v1',
          token: accessToken,
        });
        const storageService = new CloudStorageService({ apiClient });

        await storageService.downloadFile(key, localUri, (p) => setProgress(p));
        setProgress(100);
      } catch (err: unknown) {
        const errMsg = err instanceof Error ? err.message : 'Cloud download failed';
        setError(errMsg);
        throw err;
      } finally {
        setIsDownloading(false);
      }
    },
    [accessToken],
  );

  return {
    downloadFile,
    progress,
    isDownloading,
    error,
  };
}
