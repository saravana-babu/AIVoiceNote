import { useState, useCallback, useEffect } from 'react';
import { ModelManager, MODEL_PROFILES, ModelProfile } from '../ModelManager';
import { WhisperEngine, TranscriptionResult } from '../WhisperEngine';

export function useTranscription(initialProfileId = 'whisper-tiny') {
  const [selectedProfileId, setSelectedProfileId] = useState(initialProfileId);
  const [isDownloaded, setIsDownloaded] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [isModelLoaded, setIsModelLoaded] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeProfile: ModelProfile =
    MODEL_PROFILES.find((p) => p.id === selectedProfileId) || MODEL_PROFILES[0];

  // Check if active profile is downloaded on mount or selection change
  const checkDownloadStatus = useCallback(async () => {
    try {
      const status = await ModelManager.isModelDownloaded(selectedProfileId);
      setIsDownloaded(status);
      if (status) {
        setDownloadProgress(1.0);
      } else {
        setDownloadProgress(0);
      }
    } catch (err) {
      console.warn('Failed to check download status', err);
      setIsDownloaded(false);
    }
  }, [selectedProfileId]);

  useEffect(() => {
    checkDownloadStatus();
  }, [checkDownloadStatus]);

  // Download the selected model
  const downloadModel = useCallback(async () => {
    setIsDownloading(true);
    setError(null);
    try {
      await ModelManager.downloadModel(selectedProfileId, (progress) => {
        setDownloadProgress(progress);
      });
      setIsDownloaded(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Model download failed';
      setError(msg);
      setIsDownloaded(false);
    } finally {
      setIsDownloading(false);
    }
  }, [selectedProfileId]);

  // Load the model into the ONNX Runtime sessions
  const loadModel = useCallback(async () => {
    setIsModelLoading(true);
    setError(null);
    try {
      await WhisperEngine.initialize(selectedProfileId);
      setIsModelLoaded(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load model into session';
      setError(msg);
      setIsModelLoaded(false);
    } finally {
      setIsModelLoading(false);
    }
  }, [selectedProfileId]);

  // Delete the selected model to free memory
  const deleteModel = useCallback(async () => {
    setError(null);
    try {
      await WhisperEngine.release();
      await ModelManager.deleteModel(selectedProfileId);
      setIsDownloaded(false);
      setIsModelLoaded(false);
      setDownloadProgress(0);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Model deletion failed';
      setError(msg);
    }
  }, [selectedProfileId]);

  // Transcribe an audio file path/URI
  const transcribeAudio = useCallback(
    async (audioUri: string, forcedLanguage?: string): Promise<TranscriptionResult | null> => {
      setIsTranscribing(true);
      setError(null);
      try {
        // Automatically load model if downloaded but not loaded yet
        if (!isModelLoaded) {
          const downloaded = await ModelManager.isModelDownloaded(selectedProfileId);
          if (!downloaded) {
            throw new Error('Please download the model before starting transcription');
          }
          await WhisperEngine.initialize(selectedProfileId);
          setIsModelLoaded(true);
        }

        const result = await WhisperEngine.transcribeAudio(audioUri, forcedLanguage);
        return result;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Transcription failed';
        setError(msg);
        return null;
      } finally {
        setIsTranscribing(false);
      }
    },
    [selectedProfileId, isModelLoaded],
  );

  return {
    profiles: MODEL_PROFILES,
    activeProfile,
    selectedProfileId,
    setSelectedProfileId,
    isDownloaded,
    downloadProgress,
    isDownloading,
    isModelLoading,
    isModelLoaded,
    isTranscribing,
    error,
    downloadModel,
    loadModel,
    deleteModel,
    transcribeAudio,
    refreshStatus: checkDownloadStatus,
  };
}
