/**
 * Configuration settings for the VoiceMind AI mobile application.
 * Supports running in both local development (localhost) and cloud/production environments.
 */

// Expo automatically makes variables prefixed with EXPO_PUBLIC_ available in the client bundle.
const API_HOST = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

export const config = {
  API_HOST,
  API_URL: `${API_HOST}/api/v1`,
};
