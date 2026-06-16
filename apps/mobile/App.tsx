import React, { useState } from 'react';
import { StyleSheet, Text, View, SafeAreaView, ActivityIndicator } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Button } from '@voicemind/ui';
import { APP_NAME } from '@voicemind/shared';
import { useAudioRecorder } from '@voicemind/audio';
import { appStorage } from '@voicemind/storage';
import { ApiClient } from '@voicemind/api';

const apiClient = new ApiClient({ baseUrl: 'http://localhost:8000' });

export default function App() {
  const { isRecording, durationSec, uri, startRecording, stopRecording } = useAudioRecorder();
  const [apiStatus, setApiStatus] = useState<string>('checking...');
  const [loading, setLoading] = useState(false);

  const checkApi = async () => {
    setLoading(true);
    try {
      const res = await apiClient.checkHealth();
      setApiStatus(res.status);
    } catch {
      setApiStatus('offline');
    } finally {
      setLoading(false);
    }
  };

  const saveToStorage = async () => {
    if (uri) {
      await appStorage.setItem('last_recording_uri', uri);
      alert('Saved recording URI to storage!');
    } else {
      alert('No recording found to save.');
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <Text style={styles.title}>{APP_NAME}</Text>
        <Text style={styles.subtitle}>Project Foundation Verified</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Audio Module</Text>
        <Text style={styles.statusText}>
          Status: {isRecording ? `🔴 Recording (${durationSec}s)` : '⬜ Idle'}
        </Text>
        {uri && <Text style={styles.pathText}>Saved URI: {uri}</Text>}
        <View style={styles.row}>
          <Button
            title={isRecording ? 'Stop Recording' : 'Start Recording'}
            onPress={isRecording ? stopRecording : startRecording}
            variant={isRecording ? 'danger' : 'primary'}
          />
          {uri && <Button title="Save URI" onPress={saveToStorage} variant="secondary" />}
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.sectionTitle}>API Module</Text>
        <Text style={styles.statusText}>Backend API status: {apiStatus}</Text>
        {loading ? (
          <ActivityIndicator color="#007AFF" style={styles.loader} />
        ) : (
          <Button title="Ping Backend" onPress={checkApi} variant="secondary" />
        )}
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>
          apps/mobile • packages/ui, shared, audio, storage, api
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#121212',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 24,
  },
  header: {
    alignItems: 'center',
    marginTop: 40,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  subtitle: {
    fontSize: 16,
    color: '#8E8E93',
    marginTop: 8,
  },
  card: {
    backgroundColor: '#1C1C1E',
    borderRadius: 16,
    padding: 20,
    width: '100%',
    marginVertical: 12,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 12,
  },
  statusText: {
    fontSize: 15,
    color: '#E5E5EA',
    marginBottom: 16,
  },
  pathText: {
    fontSize: 13,
    color: '#007AFF',
    marginBottom: 16,
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  loader: {
    marginVertical: 12,
  },
  footer: {
    marginBottom: 20,
  },
  footerText: {
    fontSize: 12,
    color: '#48484A',
    textAlign: 'center',
  },
});
