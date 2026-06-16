import * as FileSystem from 'expo-file-system';

export interface ModelProfile {
  id: string;
  name: string;
  sizeMB: number;
  files: { name: string; url: string }[];
}

export const MODEL_PROFILES: ModelProfile[] = [
  {
    id: 'whisper-tiny',
    name: 'Whisper Tiny (Quantized)',
    sizeMB: 38,
    files: [
      {
        name: 'encoder.onnx',
        url: 'https://huggingface.co/onnx-community/whisper-tiny/resolve/main/onnx/encoder_quantized.onnx',
      },
      {
        name: 'decoder.onnx',
        url: 'https://huggingface.co/onnx-community/whisper-tiny/resolve/main/onnx/decoder_quantized.onnx',
      },
      {
        name: 'tokenizer.json',
        url: 'https://huggingface.co/onnx-community/whisper-tiny/resolve/main/tokenizer.json',
      },
      {
        name: 'config.json',
        url: 'https://huggingface.co/onnx-community/whisper-tiny/resolve/main/config.json',
      },
    ],
  },
  {
    id: 'distil-whisper-small',
    name: 'Distil-Whisper Small (Quantized)',
    sizeMB: 118,
    files: [
      {
        name: 'encoder.onnx',
        url: 'https://huggingface.co/onnx-community/distil-whisper-small-en-v1.1/resolve/main/onnx/encoder_quantized.onnx',
      },
      {
        name: 'decoder.onnx',
        url: 'https://huggingface.co/onnx-community/distil-whisper-small-en-v1.1/resolve/main/onnx/decoder_quantized.onnx',
      },
      {
        name: 'tokenizer.json',
        url: 'https://huggingface.co/onnx-community/distil-whisper-small-en-v1.1/resolve/main/tokenizer.json',
      },
      {
        name: 'config.json',
        url: 'https://huggingface.co/onnx-community/distil-whisper-small-en-v1.1/resolve/main/config.json',
      },
    ],
  },
];

export class ModelManager {
  private static mockDownloaded: Record<string, boolean> = {};

  static getModelDirectory(profileId: string): string {
    if (!FileSystem.documentDirectory) return '';
    return `${FileSystem.documentDirectory}whisper_models/${profileId}/`;
  }

  static async isModelDownloaded(profileId: string): Promise<boolean> {
    if (!FileSystem.documentDirectory) {
      return !!this.mockDownloaded[profileId];
    }

    const dir = this.getModelDirectory(profileId);
    const profile = MODEL_PROFILES.find((p) => p.id === profileId);
    if (!profile) return false;

    try {
      const dirInfo = await FileSystem.getInfoAsync(dir);
      if (!dirInfo.exists) return false;

      // Ensure all required files exist
      for (const file of profile.files) {
        const filePath = `${dir}${file.name}`;
        const fileInfo = await FileSystem.getInfoAsync(filePath);
        if (!fileInfo.exists) return false;
      }
      return true;
    } catch {
      return false;
    }
  }

  static async downloadModel(
    profileId: string,
    onProgress: (progress: number) => void,
  ): Promise<void> {
    const profile = MODEL_PROFILES.find((p) => p.id === profileId);
    if (!profile) throw new Error(`Model profile ${profileId} not found`);

    if (!FileSystem.documentDirectory) {
      // Mock progress updates on browser viewports
      let progress = 0;
      const interval = setInterval(() => {
        progress += 0.1;
        if (progress >= 1.0) {
          progress = 1.0;
          clearInterval(interval);
          this.mockDownloaded[profileId] = true;
          onProgress(1.0);
        } else {
          onProgress(progress);
        }
      }, 300);

      // Wait for mock download to complete
      await new Promise<void>((resolve) => {
        const check = setInterval(() => {
          if (progress >= 1.0) {
            clearInterval(check);
            resolve();
          }
        }, 100);
      });
      return;
    }

    const dir = this.getModelDirectory(profileId);
    // Create folder
    await FileSystem.makeDirectoryAsync(dir, { intermediates: true }).catch(() => {});

    const totalFiles = profile.files.length;
    const progressMap: Record<string, number> = {};

    for (let i = 0; i < totalFiles; i++) {
      const file = profile.files[i];
      const targetPath = `${dir}${file.name}`;

      const checkInfo = await FileSystem.getInfoAsync(targetPath);
      if (checkInfo.exists) {
        progressMap[file.name] = 1.0;
        const totalProgress = Object.values(progressMap).reduce((a, b) => a + b, 0) / totalFiles;
        onProgress(totalProgress);
        continue;
      }

      const downloadResumable = FileSystem.createDownloadResumable(
        file.url,
        targetPath,
        {},
        (downloadProgress) => {
          const fileProg =
            downloadProgress.totalBytesExpectedToWrite > 0
              ? downloadProgress.totalBytesWritten / downloadProgress.totalBytesExpectedToWrite
              : 0;
          progressMap[file.name] = fileProg;
          const totalProgress = Object.values(progressMap).reduce((a, b) => a + b, 0) / totalFiles;
          onProgress(Math.min(0.99, totalProgress));
        },
      );

      await downloadResumable.downloadAsync();
      progressMap[file.name] = 1.0;
      const currentTotalProgress =
        Object.values(progressMap).reduce((a, b) => a + b, 0) / totalFiles;
      onProgress(currentTotalProgress);
    }
  }

  static async deleteModel(profileId: string): Promise<void> {
    if (!FileSystem.documentDirectory) {
      delete this.mockDownloaded[profileId];
      return;
    }

    const dir = this.getModelDirectory(profileId);
    try {
      const dirInfo = await FileSystem.getInfoAsync(dir);
      if (dirInfo.exists) {
        await FileSystem.deleteAsync(dir, { idempotent: true });
      }
    } catch (err) {
      console.warn(`Failed to delete model files for ${profileId}`, err);
    }
  }
}
