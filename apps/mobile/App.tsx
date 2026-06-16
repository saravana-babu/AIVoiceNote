import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  View,
  SafeAreaView,
  ScrollView,
  useWindowDimensions,
  ActivityIndicator,
} from 'react-native';
import { PaperProvider, Text, Divider, Switch, useTheme } from 'react-native-paper';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  customLightTheme,
  customDarkTheme,
  Button,
  Card,
  Input,
  SearchBar,
  Modal,
  Dialog,
  BottomSheet,
  FloatingActionButton,
  RecordingButton,
  AudioWaveform,
  NoteCard,
} from '@voicemind/ui';
import { VoiceNote } from '@voicemind/shared';
import { useAuthStore } from './src/store/authStore.js';
import { useLogoutMutation } from './src/hooks/useAuth.js';
import { LoginScreen } from './src/screens/LoginScreen.js';
import { RegisterScreen } from './src/screens/RegisterScreen.js';
import { ResetPasswordScreen } from './src/screens/ResetPasswordScreen.js';

// Offline-First additions
import { initializeDatabase } from './src/database/dbSetup.js';
import { useSyncStore } from './src/store/syncStore.js';
import { useNotesQuery, useSaveNoteMutation, useDeleteNoteMutation } from './src/hooks/useNotes.js';
import { useAudioRecorder, AudioFormat, CrashRecoveryRecord } from '@voicemind/audio';
import { useTranscription, LANGUAGE_CODES } from '@voicemind/transcription';

// Setup TanStack Query Client
const queryClient = new QueryClient();

export default function App() {
  const [isDarkMode, setIsDarkMode] = useState(true);
  const theme = isDarkMode ? customDarkTheme : customLightTheme;

  // Initialize SQLite structures on startup
  useEffect(() => {
    initializeDatabase().catch((err) => {
      console.error('Failed to initialize local SQLite database', err);
    });
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <PaperProvider theme={theme}>
        <AuthGate isDarkMode={isDarkMode} setIsDarkMode={setIsDarkMode} />
      </PaperProvider>
    </QueryClientProvider>
  );
}

interface AuthGateProps {
  isDarkMode: boolean;
  setIsDarkMode: (val: boolean) => void;
}

type AuthScreen = 'login' | 'register' | 'reset_password';

function AuthGate({ isDarkMode, setIsDarkMode }: AuthGateProps) {
  const theme = useTheme();
  const { isAuthenticated, isLoading, hydrate } = useAuthStore();
  const [currentScreen, setCurrentScreen] = useState<AuthScreen>('login');

  // Hydrate auth session tokens on startup
  useEffect(() => {
    hydrate();
  }, [hydrate]);

  if (isLoading) {
    return (
      <View style={[styles.loadingCenter, { backgroundColor: theme.colors.background }]}>
        <ActivityIndicator size="large" color={theme.colors.primary} />
        <Text style={styles.loadingText}>Loading VoiceMind AI...</Text>
      </View>
    );
  }

  if (!isAuthenticated) {
    return (
      <SafeAreaView style={[styles.safeArea, { backgroundColor: theme.colors.background }]}>
        <View style={styles.authHeader}>
          <Text variant="labelLarge" style={styles.toggleText}>
            {isDarkMode ? '🌙 Dark Mode' : '☀️ Light Mode'}
          </Text>
          <Switch value={isDarkMode} onValueChange={setIsDarkMode} />
        </View>
        {currentScreen === 'login' && (
          <LoginScreen
            onNavigateToRegister={() => setCurrentScreen('register')}
            onNavigateToReset={() => setCurrentScreen('reset_password')}
          />
        )}
        {currentScreen === 'register' && (
          <RegisterScreen onNavigateToLogin={() => setCurrentScreen('login')} />
        )}
        {currentScreen === 'reset_password' && (
          <ResetPasswordScreen onNavigateToLogin={() => setCurrentScreen('login')} />
        )}
      </SafeAreaView>
    );
  }

  // Authenticated Dashboard Content
  return <MainAppContent isDarkMode={isDarkMode} setIsDarkMode={setIsDarkMode} />;
}

interface MainContentProps {
  isDarkMode: boolean;
  setIsDarkMode: (val: boolean) => void;
}

function MainAppContent({ isDarkMode, setIsDarkMode }: MainContentProps) {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;

  const { user } = useAuthStore();
  const logoutMutation = useLogoutMutation();

  // Sync state manager
  const { isOnline, isSyncing, setOnline, syncPendingNotes } = useSyncStore();

  // Offline-first hooks
  const { data: notesList = [], isLoading: isLoadingNotes } = useNotesQuery();
  const saveNoteMutation = useSaveNoteMutation();
  const deleteNoteMutation = useDeleteNoteMutation();

  // States for interactive showcase elements
  const [inputText, setInputText] = useState('');
  const [noteTitle, setNoteTitle] = useState('');
  const [noteTagsStr, setNoteTagsStr] = useState('meeting, general');
  const [playingNoteId, setPlayingNoteId] = useState<string | null>(null);
  const [playProgress, setPlayProgress] = useState(0.4);
  const [searchVal, setSearchVal] = useState('');

  // Audio recording engine state/hooks
  const [currentRecordingFormat, setCurrentRecordingFormat] = useState<AudioFormat>('m4a');
  const [activeNoteId, setActiveNoteId] = useState<string | undefined>(undefined);
  const {
    isRecording: isEngineRecording,
    isPaused: isEnginePaused,
    durationSec: recordDurationSec,
    meteringHistory,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
    checkCrashRecovery,
    clearCrashRecovery,
  } = useAudioRecorder(activeNoteId);

  const [recoveryRecord, setRecoveryRecord] = useState<CrashRecoveryRecord | null>(null);

  // On-Device Transcription Engine integration
  const [forcedLanguage, setForcedLanguage] = useState<string>('English');
  const {
    profiles: modelProfiles,
    selectedProfileId,
    setSelectedProfileId,
    isDownloaded: isModelDownloaded,
    downloadProgress: modelDownloadProgress,
    isDownloading: isModelDownloading,
    downloadModel,
    deleteModel,
    transcribeAudio,
    isTranscribing,
  } = useTranscription();

  useEffect(() => {
    async function checkRecovery() {
      const record = await checkCrashRecovery();
      if (record) {
        setRecoveryRecord(record);
      }
    }
    checkRecovery();
  }, [checkCrashRecovery]);

  // Modal, Dialog, Sheet visibility states
  const [modalVisible, setModalVisible] = useState(false);
  const [dialogVisible, setDialogVisible] = useState(false);
  const [sheetVisible, setSheetVisible] = useState(false);

  // Simulate progress when playing
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (playingNoteId) {
      interval = setInterval(() => {
        setPlayProgress((prev) => (prev >= 1 ? 0 : prev + 0.05));
      }, 500);
    }
    return () => clearInterval(interval);
  }, [playingNoteId]);

  const handleCreateNote = async () => {
    if (!noteTitle) {
      alert('Please type a note title');
      return;
    }

    const noteId = `note-${Date.now()}`;
    const tags = noteTagsStr
      .split(',')
      .map((t) => t.trim())
      .filter((t) => !!t);

    const newNote: Omit<VoiceNote, 'tags' | 'transcription' | 'summary'> = {
      id: noteId,
      title: noteTitle,
      createdAt: new Date().toISOString(),
      durationSec: 35,
      filePath: `file:///recordings/${noteId}.m4a`,
      status: 'completed',
    };

    const mockTranscript =
      'This is an offline-first voice note created locally using SQLite storage.';
    const mockSummary = 'Offline-first database creation demo.';

    try {
      await saveNoteMutation.mutateAsync({
        note: newNote,
        transcription: mockTranscript,
        summary: mockSummary,
        tags,
      });
      setNoteTitle('');
    } catch (err) {
      console.error('Save Note Error:', err);
      alert('Failed to save note');
    }
  };

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: theme.colors.background }]}>
      {/* Top Header bar with Theme Toggle */}
      <View style={[styles.header, { borderBottomColor: theme.colors.outline }]}>
        <View>
          <Text variant="headlineMedium" style={styles.title}>
            VoiceMind AI
          </Text>
          <Text variant="bodyMedium" style={{ color: theme.colors.secondary }}>
            Signed in as: {user?.displayName || user?.email}
          </Text>
        </View>
        <View style={styles.headerRight}>
          <View style={styles.toggleRow}>
            <Text variant="labelMedium" style={styles.toggleLabel}>
              {isDarkMode ? '🌙' : '☀️'}
            </Text>
            <Switch value={isDarkMode} onValueChange={setIsDarkMode} />
          </View>
          <Button
            title="Logout"
            onPress={() => logoutMutation.mutate()}
            variant="danger"
            style={styles.logoutBtn}
          />
        </View>
      </View>

      {/* Offline Status & Sync Banner */}
      <View
        style={[
          styles.syncBanner,
          { backgroundColor: isOnline ? 'rgba(20, 184, 166, 0.1)' : 'rgba(245, 158, 11, 0.1)' },
          { borderColor: isOnline ? theme.colors.secondary : '#F59E0B' },
        ]}
      >
        <View style={styles.syncLeft}>
          <Text
            variant="titleSmall"
            style={{ color: isOnline ? theme.colors.secondary : '#F59E0B' }}
          >
            {isOnline ? '🟢 Online Mode' : '🟡 Offline Mode (SQLite queueing)'}
          </Text>
          <Text variant="bodySmall" style={styles.syncSubtext}>
            {isOnline ? 'Changes are automatically synced.' : 'Database mutations are queued.'}
          </Text>
        </View>
        <View style={styles.syncControls}>
          <Switch value={isOnline} onValueChange={setOnline} />
          <Button
            title={isSyncing ? 'Syncing...' : 'Sync Now'}
            onPress={syncPendingNotes}
            variant="secondary"
            disabled={!isOnline || isSyncing}
            style={styles.syncNowBtn}
          />
        </View>
      </View>

      {recoveryRecord && (
        <Card style={StyleSheet.flatten([styles.recoveryCard, { marginHorizontal: 16 }])}>
          <Text variant="titleMedium" style={{ color: theme.colors.error, fontWeight: '700' }}>
            ⚠️ Interrupted Recording Detected
          </Text>
          <Text variant="bodyMedium" style={{ marginVertical: 8 }}>
            An active recording session from {new Date(recoveryRecord.startedAt).toLocaleString()}{' '}
            was interrupted.
          </Text>
          <View style={styles.rowGapHorizontal}>
            <Button
              title="Recover Note"
              onPress={async () => {
                const noteId = recoveryRecord.noteId;
                const newNote = {
                  id: noteId,
                  title: `Recovered Note (${recoveryRecord.format.toUpperCase()})`,
                  createdAt: recoveryRecord.startedAt,
                  durationSec: 0,
                  filePath: recoveryRecord.tempUri,
                  status: 'completed' as const,
                };
                await saveNoteMutation.mutateAsync({
                  note: newNote,
                  transcription: 'Recovered from interrupted recording session.',
                  summary: 'Crash recovery note.',
                  tags: ['recovered', recoveryRecord.format],
                });
                await clearCrashRecovery();
                setRecoveryRecord(null);
                alert('Note recovered successfully!');
              }}
              style={styles.recoveryBtn}
            />
            <Button
              title="Discard"
              variant="danger"
              onPress={async () => {
                await clearCrashRecovery();
                setRecoveryRecord(null);
              }}
              style={styles.recoveryBtn}
            />
          </View>
        </Card>
      )}

      <ScrollView contentContainerStyle={styles.scrollContainer}>
        {/* Responsive Grid Setup */}
        <View style={[styles.grid, isDesktop ? styles.desktopGrid : styles.mobileGrid]}>
          {/* Column 1: Offline Notes list */}
          <View style={[styles.column, isDesktop ? styles.desktopColumn : null]}>
            <Text variant="titleLarge" style={styles.sectionHeader}>
              Voice Notes ({notesList.length})
            </Text>

            {isLoadingNotes ? (
              <ActivityIndicator color={theme.colors.primary} style={styles.loader} />
            ) : notesList.length === 0 ? (
              <Card style={styles.cardSpacing}>
                <Text style={styles.emptyText}>
                  No local voice notes found. Create one to test SQLite storage!
                </Text>
              </Card>
            ) : (
              notesList.map((note) => {
                const isPlaying = playingNoteId === note.id;
                // Add sync visual indicators
                const isSynced =
                  (note as VoiceNote & { sync_status?: string }).sync_status === 'synced';
                const noteWithSyncTitle = {
                  ...note,
                  title: `${isSynced ? '☁️' : '⏳'} ${note.title}`,
                };

                return (
                  <NoteCard
                    key={note.id}
                    note={noteWithSyncTitle}
                    isPlaying={isPlaying}
                    playbackProgress={playProgress}
                    onPlayPause={() => {
                      if (isPlaying) {
                        setPlayingNoteId(null);
                      } else {
                        setPlayingNoteId(note.id);
                        setPlayProgress(0);
                      }
                    }}
                    onDelete={() => deleteNoteMutation.mutate(note.id)}
                    onTagPress={(tag) => setSearchVal(tag)}
                  />
                );
              })
            )}

            <Card style={styles.cardSpacing}>
              <Text variant="titleMedium" style={styles.cardHeader}>
                Create Voice Note (SQLite Database)
              </Text>
              <Input
                label="Note Title"
                value={noteTitle}
                onChangeText={setNoteTitle}
                placeholder="e.g. Design review meeting"
                style={styles.fieldSpacing}
              />
              <Input
                label="Tags (Comma separated)"
                value={noteTagsStr}
                onChangeText={setNoteTagsStr}
                placeholder="tag1, tag2"
                style={styles.fieldSpacing}
              />
              <Button title="Save to Local SQLite" onPress={handleCreateNote} />
            </Card>
          </View>

          {/* Column 2: Components UI catalog */}
          <View style={[styles.column, isDesktop ? styles.desktopColumn : null]}>
            <Text variant="titleLarge" style={styles.sectionHeader}>
              UI Components Catalog
            </Text>

            <Card style={styles.cardSpacing}>
              <Text variant="titleMedium" style={styles.cardHeader}>
                Recording Trigger & Waveforms
              </Text>
              <View style={styles.centerRow}>
                <RecordingButton
                  isRecording={isEngineRecording}
                  onPress={async () => {
                    if (isEngineRecording) {
                      const meta = await stopRecording();
                      if (meta) {
                        const noteId = activeNoteId || `note-${Date.now()}`;

                        let transcribedText = 'Transcription failed / skipped.';
                        let detectedLanguage = 'English';

                        if (isModelDownloaded) {
                          const res = await transcribeAudio(meta.uri, forcedLanguage);
                          if (res) {
                            transcribedText = res.text;
                            detectedLanguage = res.language;
                          }
                        } else {
                          transcribedText =
                            'Audio recorded. Model not downloaded, transcription skipped.';
                        }

                        const newNote = {
                          id: noteId,
                          title: `Voice Note ${new Date().toLocaleTimeString()}`,
                          createdAt: new Date().toISOString(),
                          durationSec: meta.durationSec,
                          filePath: meta.uri,
                          status: 'completed' as const,
                        };
                        await saveNoteMutation.mutateAsync({
                          note: newNote,
                          transcription: transcribedText,
                          summary: `VoiceMind Local ${detectedLanguage} Transcription`,
                          tags: ['recording', meta.format, detectedLanguage.toLowerCase()],
                        });
                        setActiveNoteId(undefined);
                        alert('Recording saved to local SQLite database!');
                      }
                    } else {
                      const newId = `note-${Date.now()}`;
                      setActiveNoteId(newId);
                      await startRecording(currentRecordingFormat);
                    }
                  }}
                />
                <View style={{ flex: 1 }}>
                  <Text style={styles.recordingLabel}>
                    {isTranscribing
                      ? 'Transcribing audio on-device...'
                      : isEngineRecording
                        ? `Recording active: ${Math.floor(recordDurationSec / 60)
                            .toString()
                            .padStart(2, '0')}:${(recordDurationSec % 60)
                            .toString()
                            .padStart(2, '0')}`
                        : 'Tap circle to record'}
                  </Text>
                  {!isEngineRecording && (
                    <>
                      <View style={styles.formatRow}>
                        {(['m4a', 'wav', 'mp3'] as AudioFormat[]).map((fmt) => (
                          <Button
                            key={fmt}
                            title={fmt.toUpperCase()}
                            onPress={() => setCurrentRecordingFormat(fmt)}
                            variant={currentRecordingFormat === fmt ? 'primary' : 'secondary'}
                            style={styles.formatBtn}
                          />
                        ))}
                      </View>
                      <View style={[styles.formatRow, { marginTop: 12 }]}>
                        <Text
                          variant="labelMedium"
                          style={{ marginRight: 6, color: theme.colors.secondary }}
                        >
                          Lang:
                        </Text>
                        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                          {Object.keys(LANGUAGE_CODES).map((lang) => (
                            <Button
                              key={lang}
                              title={lang}
                              onPress={() => setForcedLanguage(lang)}
                              variant={forcedLanguage === lang ? 'primary' : 'secondary'}
                              style={StyleSheet.flatten([styles.formatBtn, { marginRight: 6 }])}
                            />
                          ))}
                        </ScrollView>
                      </View>
                    </>
                  )}
                  {isEngineRecording && (
                    <Button
                      title={isEnginePaused ? 'Resume' : 'Pause'}
                      onPress={isEnginePaused ? resumeRecording : pauseRecording}
                      variant="secondary"
                      style={styles.controlBtn}
                    />
                  )}
                </View>
              </View>
              <Divider style={styles.divider} />
              <Text variant="bodySmall" style={styles.subtext}>
                Dynamic Waveform (Active during recording)
              </Text>
              <AudioWaveform isRecording={isEngineRecording} meteringHistory={meteringHistory} />
            </Card>

            <Card style={styles.cardSpacing}>
              <Text variant="titleMedium" style={styles.cardHeader}>
                Whisper On-Device Model Downloader
              </Text>
              <Text variant="bodySmall" style={styles.subtext}>
                Download and select the Whisper model profile to run transcription locally on the
                device offline.
              </Text>

              <View style={styles.fieldSpacing}>
                <Text variant="labelLarge" style={{ marginBottom: 6, fontWeight: '700' }}>
                  Select Profile:
                </Text>
                {modelProfiles.map((p) => (
                  <Button
                    key={p.id}
                    title={`${p.name} (${p.sizeMB} MB)`}
                    onPress={() => setSelectedProfileId(p.id)}
                    variant={selectedProfileId === p.id ? 'primary' : 'secondary'}
                    style={styles.fieldSpacing}
                    disabled={isModelDownloading}
                  />
                ))}
              </View>

              <View style={styles.rowGapHorizontal}>
                {!isModelDownloaded ? (
                  <Button
                    title={
                      isModelDownloading
                        ? `Downloading (${Math.round(modelDownloadProgress * 100)}%)`
                        : 'Download Model'
                    }
                    onPress={downloadModel}
                    loading={isModelDownloading}
                    style={{ flex: 1 }}
                  />
                ) : (
                  <>
                    <Button
                      title="Delete Model"
                      variant="danger"
                      onPress={deleteModel}
                      style={{ flex: 1 }}
                    />
                    <Text style={[styles.successText, { marginLeft: 12, alignSelf: 'center' }]}>
                      🟢 Downloaded
                    </Text>
                  </>
                )}
              </View>
            </Card>

            <Card style={styles.cardSpacing}>
              <Text variant="titleMedium" style={styles.cardHeader}>
                Text Inputs & Buttons
              </Text>
              <SearchBar
                value={searchVal}
                onChangeText={setSearchVal}
                onClear={() => setSearchVal('')}
                style={styles.fieldSpacing}
              />
              <Input
                label="Sample Input"
                value={inputText}
                onChangeText={setInputText}
                placeholder="Type something..."
              />
              <Divider style={styles.divider} />
              <View style={styles.rowGap}>
                <Button title="Open Standard Modal" onPress={() => setModalVisible(true)} />
                <Button
                  title="Open Slide Sheet"
                  onPress={() => setSheetVisible(true)}
                  variant="secondary"
                />
                <Button
                  title="Open Alert Dialog"
                  onPress={() => setDialogVisible(true)}
                  variant="secondary"
                />
              </View>
            </Card>
          </View>
        </View>
      </ScrollView>

      {/* Standard Overlay Modal */}
      <Modal visible={modalVisible} onDismiss={() => setModalVisible(false)}>
        <Text variant="headlineSmall" style={styles.overlayTitle}>
          Responsive Modal
        </Text>
        <Text variant="bodyMedium" style={styles.overlayBody}>
          This container restricts its width automatically on desktop/tablet to maintain clean
          readability.
        </Text>
        <Button title="Close Modal" onPress={() => setModalVisible(false)} />
      </Modal>

      {/* Alert Dialog */}
      <Dialog
        visible={dialogVisible}
        onDismiss={() => setDialogVisible(false)}
        title="Confirm Action"
        content="Are you sure you want to proceed with this configuration?"
        confirmLabel="Yes, Proceed"
        onConfirm={() => {
          setDialogVisible(false);
          alert('Action Confirmed');
        }}
        cancelLabel="Cancel"
        onCancel={() => setDialogVisible(false)}
      />

      {/* Responsive Slide Sheet / Drawer */}
      <BottomSheet visible={sheetVisible} onDismiss={() => setSheetVisible(false)}>
        <Text variant="headlineSmall" style={styles.overlayTitle}>
          {isDesktop ? 'Sliding Drawer (Desktop)' : 'Bottom Sheet (Mobile)'}
        </Text>
        <Text variant="bodyMedium" style={styles.overlayBody}>
          This panel adapts beautifully to your screens: it slides up from the bottom on mobile
          devices, and emerges smoothly from the right on wide desktop viewports.
        </Text>
        <Button title="Dismiss Panel" onPress={() => setSheetVisible(false)} />
      </BottomSheet>

      {/* Floating Action Button (FAB) */}
      <FloatingActionButton
        icon="plus"
        label={isDesktop ? 'New Note' : undefined}
        onPress={() => alert('New note action triggered')}
        style={styles.fabCustom}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  loadingCenter: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    fontWeight: '600',
  },
  safeArea: {
    flex: 1,
  },
  authHeader: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 16,
    gap: 8,
  },
  toggleText: {
    marginRight: 4,
  },
  header: {
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderBottomWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  logoutBtn: {
    minHeight: 36,
    paddingVertical: 0,
  },
  title: {
    fontWeight: '800',
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  toggleLabel: {
    marginRight: 2,
  },
  syncBanner: {
    marginHorizontal: 16,
    marginTop: 12,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1.5,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
  },
  syncLeft: {
    flex: 1,
    minWidth: 200,
  },
  syncSubtext: {
    opacity: 0.7,
    marginTop: 2,
  },
  syncControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  syncNowBtn: {
    minHeight: 36,
    paddingVertical: 0,
  },
  scrollContainer: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 100, // Safe padding for FAB
  },
  grid: {
    width: '100%',
  },
  mobileGrid: {
    flexDirection: 'column',
  },
  desktopGrid: {
    flexDirection: 'row',
    gap: 24,
  },
  column: {
    flex: 1,
  },
  desktopColumn: {
    maxWidth: '50%',
  },
  sectionHeader: {
    fontWeight: '700',
    marginBottom: 16,
    paddingLeft: 4,
  },
  emptyText: {
    opacity: 0.6,
    textAlign: 'center',
    paddingVertical: 12,
  },
  cardSpacing: {
    marginBottom: 20,
  },
  cardHeader: {
    fontWeight: '700',
    marginBottom: 16,
  },
  rowGap: {
    gap: 12,
  },
  centerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  recordingLabel: {
    fontSize: 15,
    flex: 1,
  },
  divider: {
    marginVertical: 16,
  },
  subtext: {
    opacity: 0.6,
    marginBottom: 8,
  },
  fieldSpacing: {
    marginBottom: 12,
  },
  loader: {
    marginVertical: 16,
  },
  overlayTitle: {
    fontWeight: '700',
    marginBottom: 12,
  },
  overlayBody: {
    marginBottom: 20,
    lineHeight: 22,
    opacity: 0.8,
  },
  fabCustom: {
    position: 'absolute',
    margin: 24,
    right: 0,
    bottom: 0,
  },
  formatRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 8,
  },
  formatBtn: {
    minWidth: 50,
    minHeight: 28,
    paddingVertical: 0,
  },
  controlBtn: {
    marginTop: 8,
    minHeight: 28,
    paddingVertical: 0,
    alignSelf: 'flex-start',
  },
  rowGapHorizontal: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 12,
  },
  recoveryCard: {
    marginHorizontal: 16,
    marginTop: 12,
    padding: 16,
    borderWidth: 1.5,
    borderColor: '#EF4444',
    backgroundColor: 'rgba(239, 68, 68, 0.05)',
  },
  recoveryBtn: {
    flex: 1,
  },
  successText: {
    color: '#10B981',
    fontWeight: '700',
  },
});
