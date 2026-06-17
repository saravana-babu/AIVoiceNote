import * as FileSystem from 'expo-file-system';
import { ApiClient } from '@voicemind/api';

const DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024; // 5MB minimum chunk size for S3/R2

export interface CloudStorageOptions {
  apiClient: ApiClient;
  chunkSize?: number;
}

export interface ProgressCallback {
  (progress: number): void;
}

export class CloudStorageService {
  private apiClient: ApiClient;
  private chunkSize: number;

  constructor(options: CloudStorageOptions) {
    this.apiClient = options.apiClient;
    this.chunkSize = options.chunkSize || DEFAULT_CHUNK_SIZE;
  }

  /**
   * Helper utility for retrying transient network errors with exponential backoff.
   */
  private async withRetry<T>(
    fn: () => Promise<T>,
    retries = 3,
    delay = 1000,
    backoff = 2,
  ): Promise<T> {
    try {
      return await fn();
    } catch (err) {
      if (retries <= 0) throw err;
      console.warn(`CloudStorageService: Operation failed, retrying in ${delay}ms...`, err);
      await new Promise((resolve) => setTimeout(resolve, delay));
      return this.withRetry(fn, retries - 1, delay * backoff, backoff);
    }
  }

  /**
   * Uploads a file using presigned PUT URL. Best suited for smaller files (e.g. settings, metadata exports).
   * Supports background uploads, progress reporting, and retry handlers.
   */
  async uploadSingleFile(
    localUri: string,
    purpose: 'audio' | 'export',
    extension: string,
    onProgress?: ProgressCallback,
  ): Promise<string> {
    // 1. Get presigned upload URL from backend
    const { url, key } = await this.apiClient.getPresignedUploadUrl(purpose, extension);

    // 2. Create the upload task with progress listener
    const uploadTask = FileSystem.createUploadTask(
      url,
      localUri,
      {
        httpMethod: 'PUT',
        uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
        sessionType: FileSystem.FileSystemSessionType.BACKGROUND,
      },
      (data: FileSystem.UploadProgressData) => {
        if (onProgress && data.totalBytesExpectedToSend > 0) {
          const progress = (data.totalBytesSent / data.totalBytesExpectedToSend) * 100;
          onProgress(progress);
        }
      },
    );

    // 3. Execute upload with retry wrappers
    await this.withRetry(async () => {
      const result = await uploadTask.uploadAsync();
      if (!result || result.status < 200 || result.status >= 300) {
        throw new Error(`Single file upload failed with status code ${result?.status}`);
      }
    });

    return key;
  }

  /**
   * Uploads a large file using S3/R2 Multipart upload API.
   * Chunks are sliced client-side using position offsets and uploaded sequentially.
   * Supports progress reporting and retry handlers per chunk.
   */
  async uploadMultipartFile(
    localUri: string,
    purpose: 'audio' | 'export',
    extension: string,
    onProgress?: ProgressCallback,
  ): Promise<string> {
    const fileInfo = await FileSystem.getInfoAsync(localUri);
    if (!fileInfo.exists) {
      throw new Error(`Local file not found for upload: ${localUri}`);
    }

    const fileSize = fileInfo.size;
    const totalParts = Math.ceil(fileSize / this.chunkSize);

    // 1. Initiate Multipart upload on backend
    const { upload_id, key } = await this.apiClient.initiateMultipartUpload(purpose, extension);

    const uploadedParts: { part_number: number; etag: string }[] = [];

    try {
      // 2. Presign all parts at once to minimize round trips
      const partNumbers = Array.from({ length: totalParts }, (_, i) => i + 1);
      const { parts: presignedUrls } = await this.apiClient.getMultipartPresignedParts(
        key,
        upload_id,
        partNumbers,
      );

      // 3. Slice and upload each chunk sequentially
      for (let i = 0; i < totalParts; i++) {
        const partNumber = i + 1;
        const offset = i * this.chunkSize;
        const length = Math.min(this.chunkSize, fileSize - offset);

        const partUrlObject = presignedUrls.find((p) => p.part_number === partNumber);
        if (!partUrlObject) {
          throw new Error(`Failed to find presigned URL for part number ${partNumber}`);
        }

        // A. Read chunk from file as Base64 string using offsets
        const base64Chunk = await FileSystem.readAsStringAsync(localUri, {
          encoding: FileSystem.EncodingType.Base64,
          position: offset,
          length: length,
        });

        // B. Write to a temporary file in local cache
        const tempChunkUri = `${FileSystem.cacheDirectory}voicemind_chunk_${partNumber}`;
        await FileSystem.writeAsStringAsync(tempChunkUri, base64Chunk, {
          encoding: FileSystem.EncodingType.Base64,
        });

        // C. Upload chunk with retries
        try {
          const etag = await this.withRetry(async () => {
            const uploadResult = await FileSystem.uploadAsync(partUrlObject.url, tempChunkUri, {
              httpMethod: 'PUT',
              uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
            });

            if (uploadResult.status < 200 || uploadResult.status >= 300) {
              throw new Error(
                `Failed to upload chunk ${partNumber}. Status: ${uploadResult.status}`,
              );
            }

            const headerEtag = uploadResult.headers['ETag'] || uploadResult.headers['etag'];
            if (!headerEtag) {
              throw new Error(`ETag header not returned for chunk ${partNumber}`);
            }

            // Standardize ETag quotes
            return headerEtag.replace(/"/g, '');
          });

          uploadedParts.push({ part_number: partNumber, etag });

          // Report overall progress
          if (onProgress) {
            onProgress(((i + 1) / totalParts) * 100);
          }
        } finally {
          // Clean up temp file immediately after chunk upload
          await FileSystem.deleteAsync(tempChunkUri, { idempotent: true });
        }
      }

      // 4. Complete the Multipart upload on backend
      await this.apiClient.completeMultipartUpload(key, upload_id, uploadedParts);
      return key;
    } catch (error) {
      // Abort multipart upload on R2 if any part upload fails to clean up storage
      try {
        await this.apiClient.abortMultipartUpload(key, upload_id);
      } catch (abortError) {
        console.error('Failed to abort multipart upload after initial failure:', abortError);
      }
      throw error;
    }
  }

  /**
   * Downloads a file from R2 using a presigned GET URL.
   * Supports background downloads, progress callbacks, and retries.
   */
  async downloadFile(key: string, localUri: string, onProgress?: ProgressCallback): Promise<void> {
    // 1. Get presigned GET URL from backend
    const { url } = await this.apiClient.getPresignedDownloadUrl(key);

    // 2. Create the download task using createDownloadResumable
    const downloadResumable = FileSystem.createDownloadResumable(
      url,
      localUri,
      {
        sessionType: FileSystem.FileSystemSessionType.BACKGROUND,
      },
      (data: FileSystem.DownloadProgressData) => {
        if (onProgress && data.totalBytesExpectedToWrite > 0) {
          const progress = (data.totalBytesWritten / data.totalBytesExpectedToWrite) * 100;
          onProgress(progress);
        }
      },
    );

    // 3. Execute download task with retries
    await this.withRetry(async () => {
      const result = await downloadResumable.downloadAsync();
      if (!result || result.status < 200 || result.status >= 300) {
        throw new Error(`File download failed with status code ${result?.status}`);
      }
    });
  }
}
