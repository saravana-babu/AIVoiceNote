import { useState, useCallback, useEffect, useRef } from 'react';
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';
import { appStorage } from '@voicemind/storage';

export type AudioFormat = 'm4a' | 'wav' | 'mp3';

export interface AudioMetadata {
  uri: string;
  durationSec: number;
  fileSize: number;
  format: AudioFormat;
  mimeType: string;
}

export interface CrashRecoveryRecord {
  noteId: string;
  tempUri: string;
  format: AudioFormat;
  startedAt: string;
}

export function useAudioRecorder(activeNoteId?: string) {
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [durationSec, setDurationSec] = useState(0);
  const [meteringHistory, setMeteringHistory] = useState<number[]>([]);
  const [recordingUri, setRecordingUri] = useState<string | null>(null);

  const recordingRef = useRef<Audio.Recording | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const isWebOrDesktop = useRef(false);

  // Check if native audio modules are available, else fallback to web mock
  useEffect(() => {
    async function checkPlatform() {
      try {
        await Audio.getPermissionsAsync();
      } catch {
        isWebOrDesktop.current = true;
      }
    }
    checkPlatform();
  }, []);

  // --- METERING HELPER (dB to 0.0 - 1.0 range) ---
  const normalizeMetering = (dbValue: number | undefined): number => {
    if (dbValue === undefined) return 0.1;
    // expo-av metering values range from -160dB to 0dB
    if (dbValue < -160) return 0.05;
    if (dbValue >= 0) return 1.0;
    // Map -160..0 to 0..1 exponentially/logarithmically for visualization
    const normalized = (dbValue + 160) / 160;
    return Math.max(0.05, Math.min(1.0, normalized));
  };

  // --- START RECORDING ---
  const startRecording = useCallback(
    async (format: AudioFormat = 'm4a') => {
      setDurationSec(0);
      setMeteringHistory([]);
      setRecordingUri(null);
      setIsPaused(false);

      if (isWebOrDesktop.current) {
        // Mock web/desktop recording
        setIsRecording(true);
        let elapsed = 0;
        timerRef.current = setInterval(() => {
          elapsed += 1;
          setDurationSec(elapsed);
          // Generate mock waveform coordinates
          setMeteringHistory((prev) => [...prev, 0.2 + Math.random() * 0.7]);
        }, 1000);
        return;
      }

      try {
        // 1. Request microphone permissions
        const permission = await Audio.requestPermissionsAsync();
        if (!permission.granted) {
          throw new Error('Microphone permission not granted');
        }

        // 2. Configure audio mode for recording (enables background recording)
        await Audio.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
          staysActiveInBackground: true,
          playThroughEarpieceAndroid: false,
        });

        // 3. Define Recording Options based on target format
        let options: Audio.RecordingOptions;
        if (format === 'wav') {
          // PCM Wav 16bit mono
          options = {
            android: {
              extension: '.wav',
              outputFormat: 3, // AMR_NB or similar, but PCM is usually configured:
              audioEncoder: 3,
              sampleRate: 16000,
              numberOfChannels: 1,
              bitRate: 256000,
            },
            ios: {
              extension: '.wav',
              audioQuality: 127,
              sampleRate: 16000,
              numberOfChannels: 1,
              bitRate: 256000,
              linearPCMBitDepth: 16,
              linearPCMIsBigEndian: false,
              linearPCMIsFloat: false,
            },
            web: {
              mimeType: 'audio/wav',
              bitsPerSecond: 128000,
            },
          };
        } else {
          // Default to high quality M4A (AAC) preset
          options = Audio.RecordingOptionsPresets.HIGH_QUALITY;
        }

        // Enable metering (sound level checking)
        options.isMeteringEnabled = true;

        // 4. Instantiate and load
        const recording = new Audio.Recording();
        await recording.prepareToRecordAsync(options);

        // 5. Status updates callback (metering & duration)
        recording.setOnRecordingStatusUpdate((status) => {
          if (status.canRecord) {
            setDurationSec(Math.round(status.durationMillis / 1000));
            if (status.isRecording && status.metering !== undefined) {
              const amp = normalizeMetering(status.metering);
              setMeteringHistory((prev) => [...prev, amp]);
            }
          }
        });

        // 6. Start!
        await recording.startAsync();
        recordingRef.current = recording;
        setIsRecording(true);

        // 7. Write Crash Recovery data to storage
        if (activeNoteId) {
          const tempUri = recording.getURI() || '';
          const recoveryRecord: CrashRecoveryRecord = {
            noteId: activeNoteId,
            tempUri,
            format,
            startedAt: new Date().toISOString(),
          };
          await appStorage.setItem('crash_recovery_record', JSON.stringify(recoveryRecord));
        }
      } catch (err) {
        console.error('Failed to start recording', err);
        throw err;
      }
    },
    [activeNoteId],
  );

  // --- PAUSE RECORDING ---
  const pauseRecording = useCallback(async () => {
    if (isWebOrDesktop.current) {
      setIsPaused(true);
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    try {
      const recording = recordingRef.current;
      if (recording) {
        await recording.pauseAsync();
        setIsPaused(true);
      }
    } catch (err) {
      console.error('Failed to pause recording', err);
    }
  }, []);

  // --- RESUME RECORDING ---
  const resumeRecording = useCallback(async () => {
    if (isWebOrDesktop.current) {
      setIsPaused(false);
      let elapsed = durationSec;
      timerRef.current = setInterval(() => {
        elapsed += 1;
        setDurationSec(elapsed);
        setMeteringHistory((prev) => [...prev, 0.2 + Math.random() * 0.7]);
      }, 1000);
      return;
    }

    try {
      const recording = recordingRef.current;
      if (recording) {
        await recording.startAsync();
        setIsPaused(false);
      }
    } catch (err) {
      console.error('Failed to resume recording', err);
    }
  }, [durationSec]);

  // --- STOP RECORDING & EXTRA METADATA ---
  const stopRecording = useCallback(async (): Promise<AudioMetadata | null> => {
    setIsRecording(false);
    setIsPaused(false);

    if (isWebOrDesktop.current) {
      if (timerRef.current) clearInterval(timerRef.current);
      // Return mock web metadata
      const mockUri = 'file://mock-recordings/recording.m4a';
      setRecordingUri(mockUri);
      return {
        uri: mockUri,
        durationSec: durationSec || 15,
        fileSize: 1024 * 150, // 150 KB
        format: 'm4a',
        mimeType: 'audio/m4a',
      };
    }

    try {
      const recording = recordingRef.current;
      if (!recording) return null;

      // Stop recording session
      await recording.stopAndUnloadAsync();
      const tempUri = recording.getURI();
      recordingRef.current = null;

      if (!tempUri) throw new Error('Recording finished but URI is missing');

      // 1. Move file to persistent Document Directory
      const filename = `recording_${Date.now()}.m4a`;
      const targetUri = `${FileSystem.documentDirectory}${filename}`;
      await FileSystem.moveAsync({
        from: tempUri,
        to: targetUri,
      });

      // 2. Fetch File details (file size)
      const fileInfo = await FileSystem.getInfoAsync(targetUri);
      const fileSize = fileInfo.exists ? fileInfo.size : 0;

      // 3. Clear recovery session records
      await appStorage.removeItem('crash_recovery_record');

      setRecordingUri(targetUri);

      return {
        uri: targetUri,
        durationSec,
        fileSize,
        format: 'm4a', // Default format
        mimeType: 'audio/m4a',
      };
    } catch (err) {
      console.error('Failed to stop recording', err);
      return null;
    }
  }, [durationSec]);

  // --- CHECK CRASH RECOVERY ---
  const checkCrashRecovery = useCallback(async (): Promise<CrashRecoveryRecord | null> => {
    try {
      const recordStr = await appStorage.getItem('crash_recovery_record');
      if (recordStr) {
        return JSON.parse(recordStr) as CrashRecoveryRecord;
      }
    } catch (err) {
      console.error('Failed to check crash recovery', err);
    }
    return null;
  }, []);

  const clearCrashRecovery = useCallback(async () => {
    await appStorage.removeItem('crash_recovery_record');
  }, []);

  return {
    isRecording,
    isPaused,
    durationSec,
    meteringHistory,
    recordingUri,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
    checkCrashRecovery,
    clearCrashRecovery,
  };
}
