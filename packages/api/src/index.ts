import { VoiceNote } from '@voicemind/shared';

export interface ApiClientConfig {
  baseUrl: string;
  token?: string;
}

export class ApiClient {
  private config: ApiClientConfig;

  constructor(config: ApiClientConfig) {
    this.config = config;
  }

  setToken(token: string) {
    this.config.token = token;
  }

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (this.config.token) {
      headers['Authorization'] = `Bearer ${this.config.token}`;
    }
    return headers;
  }

  async checkHealth(): Promise<{ status: string }> {
    const res = await fetch(`${this.config.baseUrl}/health`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('API Health Check failed');
    return res.json();
  }

  async getNotes(): Promise<VoiceNote[]> {
    const res = await fetch(`${this.config.baseUrl}/notes`, {
      headers: this.getHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch voice notes');
    return res.json();
  }

  async uploadAudio(fileUri: string): Promise<VoiceNote> {
    const formData = new FormData();
    // In React Native, FormData requires an object structure for files
    formData.append('file', {
      uri: fileUri,
      name: 'recording.m4a',
      type: 'audio/m4a',
    } as unknown as Blob);

    const res = await fetch(`${this.config.baseUrl}/notes/upload`, {
      method: 'POST',
      headers: {
        // Content-Type is set automatically by the browser/native fetch for FormData
        ...(this.config.token ? { Authorization: `Bearer ${this.config.token}` } : {}),
      },
      body: formData,
    });

    if (!res.ok) throw new Error('Audio upload failed');
    return res.json();
  }
}
