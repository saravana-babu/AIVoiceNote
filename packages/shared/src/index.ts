export interface VoiceNote {
  id: string;
  title: string;
  createdAt: string;
  durationSec: number;
  filePath: string;
  status: 'recording' | 'transcribing' | 'completed' | 'failed';
  transcription?: string;
  summary?: string;
  tags: string[];
}

export interface UserProfile {
  id: string;
  email: string;
  displayName?: string;
}

export const APP_NAME = 'VoiceMind AI';
