import { MD3LightTheme, MD3DarkTheme } from 'react-native-paper';

// Premium custom Indigo/Teal color palette for VoiceMind AI
export const customLightTheme = {
  ...MD3LightTheme,
  colors: {
    ...MD3LightTheme.colors,
    primary: '#4F46E5', // Indigo
    primaryContainer: '#E0E7FF',
    secondary: '#0D9488', // Teal
    secondaryContainer: '#CCFBF1',
    background: '#F9FAFB', // Cool grey background
    surface: '#FFFFFF',
    surfaceVariant: '#F3F4F6',
    error: '#EF4444',
    text: '#111827',
    onPrimary: '#FFFFFF',
    onSecondary: '#FFFFFF',
    onBackground: '#111827',
    onSurface: '#111827',
    outline: '#D1D5DB',
  },
};

export const customDarkTheme = {
  ...MD3DarkTheme,
  colors: {
    ...MD3DarkTheme.colors,
    primary: '#6366F1', // Indigo Neon
    primaryContainer: '#312E81',
    secondary: '#14B8A6', // Teal Neon
    secondaryContainer: '#115E59',
    background: '#0F172A', // Sleek dark slate
    surface: '#1E293B', // Slate surface
    surfaceVariant: '#334155',
    error: '#F87171',
    text: '#F8FAFC',
    onPrimary: '#FFFFFF',
    onSecondary: '#FFFFFF',
    onBackground: '#F8FAFC',
    onSurface: '#F8FAFC',
    outline: '#475569',
  },
};
