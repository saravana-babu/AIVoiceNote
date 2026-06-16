import { useState, useCallback } from 'react';

export interface AudioRecordingState {
  isRecording: boolean;
  durationSec: number;
  uri: string | null;
}

export function useAudioRecorder() {
  const [state, setState] = useState<AudioRecordingState>({
    isRecording: false,
    durationSec: 0,
    uri: null,
  });

  const startRecording = useCallback(async () => {
    // Mock implementation for foundation
    setState({
      isRecording: true,
      durationSec: 0,
      uri: null,
    });
  }, []);

  const stopRecording = useCallback(async () => {
    // Mock implementation for foundation
    setState((prev) => ({
      ...prev,
      isRecording: false,
      uri: 'file://mock-audio-note.m4a',
    }));
  }, []);

  return {
    ...state,
    startRecording,
    stopRecording,
  };
}

export interface AudioPlaybackState {
  isPlaying: boolean;
  positionSec: number;
}

export function useAudioPlayer(uri: string | null) {
  const [state, setState] = useState<AudioPlaybackState>({
    isPlaying: false,
    positionSec: 0,
  });

  const play = useCallback(async () => {
    if (!uri) return;
    setState({ isPlaying: true, positionSec: 0 });
  }, [uri]);

  const pause = useCallback(async () => {
    setState((prev) => ({ ...prev, isPlaying: false }));
  }, []);

  return {
    ...state,
    play,
    pause,
  };
}
