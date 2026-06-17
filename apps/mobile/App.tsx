import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  View,
  SafeAreaView,
  ScrollView,
  useWindowDimensions,
  ActivityIndicator,
  Alert,
  TouchableOpacity,
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
import {
  useMeetingMinutesQuery,
  useGenerateMinutesMutation,
  useDeleteMinutesMutation,
} from './src/hooks/useMeetingMinutes.js';
import { useSearchQuery } from './src/hooks/useSearch.js';
import {
  useScheduledEmailsQuery,
  useSendEmailNowMutation,
  useScheduleEmailMutation,
  useCancelScheduledEmailMutation,
} from './src/hooks/useEmail.js';
import {
  useNoteEnhancementsQuery,
  useGenerateEnhancementMutation,
  useDeleteEnhancementMutation,
} from './src/hooks/useEnhancement.js';
import { KnowledgeHubView } from './src/components/KnowledgeHubView.js';

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

  const [activeMainTab, setActiveMainTab] = useState<'notes' | 'knowledge'>('notes');

  const { user } = useAuthStore();
  const logoutMutation = useLogoutMutation();

  // Sync state manager
  const { isOnline, isSyncing, setOnline, syncPendingNotes } = useSyncStore();

  // Offline-first hooks
  const { data: notesList = [], isLoading: isLoadingNotes } = useNotesQuery();
  const saveNoteMutation = useSaveNoteMutation();
  const deleteNoteMutation = useDeleteNoteMutation();

  // States for interactive showcase elements
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
  const [inputText, setInputText] = useState('');
  const [noteTitle, setNoteTitle] = useState('');
  const [noteTagsStr, setNoteTagsStr] = useState('meeting, general');
  const [playingNoteId, setPlayingNoteId] = useState<string | null>(null);
  const [playProgress, setPlayProgress] = useState(0.4);
  const [searchVal, setSearchVal] = useState('');
  const [searchType, setSearchType] = useState<'semantic' | 'fts' | 'hybrid'>('hybrid');

  const { data: searchResults = [], isLoading: isLoadingSearch } = useSearchQuery(
    searchVal,
    searchType,
  );
  const isSearching = searchVal.trim().length >= 2;

  const [emailModalVisible, setEmailModalVisible] = useState(false);
  const [emailRecipient, setEmailRecipient] = useState('');
  const [emailSubject, setEmailSubject] = useState('');
  const [includeTranscript, setIncludeTranscript] = useState(true);
  const [includeSummary, setIncludeSummary] = useState(true);
  const [includeMinutes, setIncludeMinutes] = useState(true);
  const [emailScheduleMode, setEmailScheduleMode] = useState<'now' | '1h' | '4h' | '24h'>('now');
  const [emailProvider, setEmailProvider] = useState<'smtp' | 'gmail'>('smtp');

  // Hooks for email
  const { data: scheduledEmails = [], refetch: refetchScheduled } = useScheduledEmailsQuery();
  const sendEmailNowMutation = useSendEmailNowMutation();
  const scheduleEmailMutation = useScheduleEmailMutation();
  const cancelScheduledEmailMutation = useCancelScheduledEmailMutation();

  useEffect(() => {
    if (emailModalVisible && selectedNoteId) {
      const selectedNote = notesList.find((n) => n.id === selectedNoteId);
      if (selectedNote) {
        setEmailSubject(`VoiceMind Share: ${selectedNote.title}`);
      }
    }
  }, [emailModalVisible, selectedNoteId, notesList]);

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

  const handleSelectNote = (noteId: string) => {
    setSelectedNoteId(noteId);
    setSheetVisible(true);
  };

  const handleDismissSheet = () => {
    setSheetVisible(false);
    setSelectedNoteId(null);
  };

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
          <View style={{ flexDirection: 'row', gap: 12, marginTop: 4 }}>
            <TouchableOpacity 
              onPress={() => setActiveMainTab('notes')}
              style={{
                paddingBottom: 4,
                borderBottomWidth: activeMainTab === 'notes' ? 2 : 0,
                borderBottomColor: theme.colors.primary,
              }}
            >
              <Text style={{ fontWeight: activeMainTab === 'notes' ? '700' : '400', color: activeMainTab === 'notes' ? theme.colors.primary : theme.colors.secondary, fontSize: 13 }}>
                🎙️ Notes
              </Text>
            </TouchableOpacity>
            <TouchableOpacity 
              onPress={() => setActiveMainTab('knowledge')}
              style={{
                paddingBottom: 4,
                borderBottomWidth: activeMainTab === 'knowledge' ? 2 : 0,
                borderBottomColor: theme.colors.primary,
              }}
            >
              <Text style={{ fontWeight: activeMainTab === 'knowledge' ? '700' : '400', color: activeMainTab === 'knowledge' ? theme.colors.primary : theme.colors.secondary, fontSize: 13 }}>
                🧠 Knowledge Hub
              </Text>
            </TouchableOpacity>
          </View>
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

      {activeMainTab === 'notes' ? (
        <ScrollView contentContainerStyle={styles.scrollContainer}>
        {/* Responsive Grid Setup */}
        <View style={[styles.grid, isDesktop ? styles.desktopGrid : styles.mobileGrid]}>
          {/* Column 1: Offline Notes list */}
          <View style={[styles.column, isDesktop ? styles.desktopColumn : null]}>
            <Text variant="titleLarge" style={styles.sectionHeader}>
              Voice Notes ({isSearching ? searchResults.length : notesList.length})
            </Text>

            <Card style={{ ...styles.cardSpacing, padding: 12 }}>
              <SearchBar
                value={searchVal}
                onChangeText={setSearchVal}
                onClear={() => setSearchVal('')}
                placeholder="Search notes, transcripts..."
                style={{ marginBottom: isSearching ? 12 : 0 }}
              />

              {isSearching && (
                <View style={styles.searchTypeRow}>
                  <Button
                    title="🤖 Semantic"
                    onPress={() => setSearchType('semantic')}
                    variant={searchType === 'semantic' ? 'primary' : 'secondary'}
                    style={styles.chipButton}
                  />
                  <Button
                    title="📝 Text"
                    onPress={() => setSearchType('fts')}
                    variant={searchType === 'fts' ? 'primary' : 'secondary'}
                    style={styles.chipButton}
                  />
                  <Button
                    title="⚡ Hybrid"
                    onPress={() => setSearchType('hybrid')}
                    variant={searchType === 'hybrid' ? 'primary' : 'secondary'}
                    style={styles.chipButton}
                  />
                </View>
              )}
            </Card>

            {isSearching ? (
              isLoadingSearch ? (
                <ActivityIndicator color={theme.colors.primary} style={styles.loader} />
              ) : searchResults.length === 0 ? (
                <Card style={styles.cardSpacing}>
                  <Text style={styles.emptyText}>
                    No matching search results found. Try another query or switch search modes!
                  </Text>
                </Card>
              ) : (
                searchResults.map((result) => {
                  const note = result.note;
                  const isPlaying = playingNoteId === note.id;
                  const isSynced =
                    (note as VoiceNote & { sync_status?: string }).sync_status === 'synced';
                  const noteWithSyncTitle = {
                    ...note,
                    title: `${isSynced ? '☁️' : '⏳'} ${note.title}`,
                  };

                  return (
                    <View key={note.id} style={styles.searchCardContainer}>
                      <NoteCard
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
                        onPress={() => handleSelectNote(note.id)}
                      />
                      <View
                        style={[
                          styles.relevanceBadge,
                          result.match_type === 'semantic'
                            ? styles.semanticBadge
                            : result.match_type === 'fts'
                              ? styles.ftsBadge
                              : styles.hybridBadge,
                        ]}
                      >
                        <Text style={styles.badgeText}>
                          {result.match_type === 'semantic'
                            ? `✨ Semantic Match ${Math.round(result.score * 100)}%`
                            : result.match_type === 'fts'
                              ? `📝 Text Match`
                              : `⚡ Hybrid Match`}
                        </Text>
                      </View>
                    </View>
                  );
                })
              )
            ) : isLoadingNotes ? (
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
                    onPress={() => handleSelectNote(note.id)}
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
      ) : (
        <KnowledgeHubView />
      )}

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

      {/* Email Delivery Modal */}
      <Modal visible={emailModalVisible} onDismiss={() => setEmailModalVisible(false)}>
        {(() => {
          const selectedNote = notesList.find((n) => n.id === selectedNoteId);
          if (!selectedNote) return <Text>Select a note first</Text>;

          const pendingEmails = scheduledEmails.filter(
            (e) => e.note_id === selectedNote.id && e.status === 'pending',
          );

          const handleSendOrSchedule = async () => {
            if (!emailRecipient.trim()) {
              Alert.alert('Error', 'Please enter a recipient email.');
              return;
            }

            try {
              if (emailScheduleMode === 'now') {
                await sendEmailNowMutation.mutateAsync({
                  note_id: selectedNote.id,
                  recipient: emailRecipient,
                  subject: emailSubject,
                  provider: emailProvider,
                  include_transcript: includeTranscript,
                  include_summary: includeSummary,
                  include_minutes: includeMinutes,
                });
                Alert.alert('Success', 'Email sent successfully!');
              } else {
                let hours = 1;
                if (emailScheduleMode === '4h') hours = 4;
                if (emailScheduleMode === '24h') hours = 24;

                const scheduledAt = new Date(Date.now() + hours * 60 * 60 * 1000).toISOString();

                await scheduleEmailMutation.mutateAsync({
                  note_id: selectedNote.id,
                  recipient: emailRecipient,
                  subject: emailSubject,
                  provider: emailProvider,
                  include_transcript: includeTranscript,
                  include_summary: includeSummary,
                  include_minutes: includeMinutes,
                  scheduled_at: scheduledAt,
                });
                Alert.alert(
                  'Success',
                  `Email scheduled successfully for ${hours} hour(s) from now!`,
                );
              }
              setEmailModalVisible(false);
            } catch (err: any) {
              Alert.alert('Error', err.message || 'Failed to dispatch email.');
            }
          };

          return (
            <ScrollView contentContainerStyle={{ padding: 4 }}>
              <Text variant="headlineSmall" style={styles.overlayTitle}>
                📧 Email & Share Note
              </Text>

              <Input
                label="Recipient Email"
                value={emailRecipient}
                onChangeText={setEmailRecipient}
                placeholder="friend@example.com"
                style={styles.fieldSpacing}
                keyboardType="email-address"
              />

              <Input
                label="Subject"
                value={emailSubject}
                onChangeText={setEmailSubject}
                placeholder="Subject line"
                style={styles.fieldSpacing}
              />

              <Divider style={styles.divider} />

              <Text variant="labelLarge" style={{ fontWeight: '700', marginBottom: 8 }}>
                Include:
              </Text>
              <View style={[styles.rowGapHorizontal, { marginBottom: 16 }]}>
                <Button
                  title="Transcript"
                  onPress={() => setIncludeTranscript(!includeTranscript)}
                  variant={includeTranscript ? 'primary' : 'secondary'}
                  style={{ flex: 1 }}
                />
                <Button
                  title="Summaries"
                  onPress={() => setIncludeSummary(!includeSummary)}
                  variant={includeSummary ? 'primary' : 'secondary'}
                  style={{ flex: 1 }}
                />
                <Button
                  title="Minutes"
                  onPress={() => setIncludeMinutes(!includeMinutes)}
                  variant={includeMinutes ? 'primary' : 'secondary'}
                  style={{ flex: 1 }}
                />
              </View>

              <Text variant="labelLarge" style={{ fontWeight: '700', marginBottom: 8 }}>
                Delivery Provider:
              </Text>
              <View style={[styles.rowGapHorizontal, { marginBottom: 16 }]}>
                <Button
                  title="✉️ SMTP Server"
                  onPress={() => setEmailProvider('smtp')}
                  variant={emailProvider === 'smtp' ? 'primary' : 'secondary'}
                  style={{ flex: 1 }}
                />
                <Button
                  title="🤖 Gmail API"
                  onPress={() => setEmailProvider('gmail')}
                  variant={emailProvider === 'gmail' ? 'primary' : 'secondary'}
                  style={{ flex: 1 }}
                />
              </View>

              <Text variant="labelLarge" style={{ fontWeight: '700', marginBottom: 8 }}>
                Schedule Delivery:
              </Text>
              <View style={[styles.rowGapHorizontal, { marginBottom: 20 }]}>
                <Button
                  title="Send Now"
                  onPress={() => setEmailScheduleMode('now')}
                  variant={emailScheduleMode === 'now' ? 'primary' : 'secondary'}
                  style={{ flex: 1 }}
                />
                <Button
                  title="In 1h"
                  onPress={() => setEmailScheduleMode('1h')}
                  variant={emailScheduleMode === '1h' ? 'primary' : 'secondary'}
                  style={{ flex: 1 }}
                />
                <Button
                  title="In 4h"
                  onPress={() => setEmailScheduleMode('4h')}
                  variant={emailScheduleMode === '4h' ? 'primary' : 'secondary'}
                  style={{ flex: 1 }}
                />
                <Button
                  title="In 24h"
                  onPress={() => setEmailScheduleMode('24h')}
                  variant={emailScheduleMode === '24h' ? 'primary' : 'secondary'}
                  style={{ flex: 1 }}
                />
              </View>

              <View style={{ flexDirection: 'row', gap: 12, marginTop: 12 }}>
                <Button
                  title={emailScheduleMode === 'now' ? 'Send Email' : 'Schedule Delivery'}
                  onPress={handleSendOrSchedule}
                  style={{ flex: 2 }}
                  loading={sendEmailNowMutation.isPending || scheduleEmailMutation.isPending}
                />
                <Button
                  title="Cancel"
                  onPress={() => setEmailModalVisible(false)}
                  variant="secondary"
                  style={{ flex: 1 }}
                />
              </View>

              {pendingEmails.length > 0 && (
                <>
                  <Divider style={[styles.divider, { marginVertical: 16 }]} />
                  <Text variant="titleMedium" style={{ fontWeight: '700', marginBottom: 12 }}>
                    ⏳ Pending Scheduled Deliveries
                  </Text>
                  {pendingEmails.map((email) => (
                    <Card
                      key={email.id}
                      style={{
                        padding: 12,
                        marginBottom: 8,
                        backgroundColor: theme.colors.elevation.level2,
                      }}
                    >
                      <Text variant="labelMedium" style={{ fontWeight: '700' }}>
                        To: {email.recipient}
                      </Text>
                      <Text variant="bodySmall" style={{ marginVertical: 4 }}>
                        Subject: {email.subject}
                      </Text>
                      <Text variant="bodySmall" style={{ opacity: 0.8, marginBottom: 8 }}>
                        Send Time: {new Date(email.scheduled_at).toLocaleString()}
                      </Text>
                      <Button
                        title="Cancel Scheduled Delivery"
                        onPress={() => cancelScheduledEmailMutation.mutate(email.id)}
                        variant="danger"
                        loading={cancelScheduledEmailMutation.isPending}
                        style={{ alignSelf: 'flex-start' }}
                      />
                    </Card>
                  ))}
                </>
              )}
            </ScrollView>
          );
        })()}
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
      <BottomSheet visible={sheetVisible} onDismiss={handleDismissSheet}>
        {selectedNoteId ? (
          <ScrollView contentContainerStyle={{ paddingBottom: 20 }}>
            {(() => {
              const selectedNote = notesList.find((n) => n.id === selectedNoteId);
              if (!selectedNote) return <Text>Note not found</Text>;

              return (
                <View>
                  <Text variant="headlineSmall" style={styles.overlayTitle}>
                    {selectedNote.title || 'Untitled Recording'}
                  </Text>
                  <Text
                    variant="bodySmall"
                    style={{ color: theme.colors.secondary, marginBottom: 16 }}
                  >
                    Created: {new Date(selectedNote.createdAt).toLocaleString()} • Duration:{' '}
                    {selectedNote.durationSec}s
                  </Text>

                  {/* Transcript Section */}
                  <Card
                    style={StyleSheet.flatten([
                      styles.cardSpacing,
                      { backgroundColor: theme.colors.elevation.level2 },
                    ])}
                  >
                    <Text variant="titleMedium" style={{ fontWeight: '700', marginBottom: 8 }}>
                      📝 Transcription
                    </Text>
                    <Text variant="bodyMedium" style={{ lineHeight: 20, opacity: 0.9 }}>
                      {selectedNote.transcription || 'No transcription available.'}
                    </Text>
                  </Card>

                  {/* Meeting Minutes Section */}
                  <MeetingMinutesView
                    noteId={selectedNote.id}
                    transcription={selectedNote.transcription}
                    isOnline={isOnline}
                  />

                  {/* Note Enhancements Section */}
                  <NoteEnhancementsView
                    noteId={selectedNote.id}
                    transcription={selectedNote.transcription}
                    isOnline={isOnline}
                  />

                  <View style={{ flexDirection: 'row', gap: 12, marginTop: 16 }}>
                    <Button
                      title="📧 Email Note"
                      onPress={() => {
                        setEmailModalVisible(true);
                      }}
                      style={{ flex: 1 }}
                      variant="primary"
                    />
                    <Button
                      title="Close Details"
                      onPress={handleDismissSheet}
                      style={{ flex: 1 }}
                      variant="secondary"
                    />
                  </View>
                </View>
              );
            })()}
          </ScrollView>
        ) : (
          <View>
            <Text variant="headlineSmall" style={styles.overlayTitle}>
              {isDesktop ? 'Sliding Drawer (Desktop)' : 'Bottom Sheet (Mobile)'}
            </Text>
            <Text variant="bodyMedium" style={styles.overlayBody}>
              This panel adapts beautifully to your screens: it slides up from the bottom on mobile
              devices, and emerges smoothly from the right on wide desktop viewports.
            </Text>
            <Button title="Dismiss Panel" onPress={handleDismissSheet} />
          </View>
        )}
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

interface NoteEnhancementsViewProps {
  noteId: string;
  transcription?: string;
  isOnline: boolean;
}

function NoteEnhancementsView({ noteId, transcription, isOnline }: NoteEnhancementsViewProps) {
  const theme = useTheme();
  const [selectedType, setSelectedType] = useState<'improved' | 'professional' | 'blog' | 'executive_report' | 'email' | 'project_update'>('improved');
  const [selectedProvider, setSelectedProvider] = useState<'openai' | 'anthropic' | 'gemini'>('openai');

  const { data: enhancements, isLoading } = useNoteEnhancementsQuery(noteId);
  const generateEnhancement = useGenerateEnhancementMutation();
  const deleteEnhancement = useDeleteEnhancementMutation();

  const handleGenerate = async () => {
    try {
      await generateEnhancement.mutateAsync({
        noteId,
        enhancementType: selectedType,
        provider: selectedProvider,
      });
    } catch (err: any) {
      alert(err.message || 'Failed to generate enhancement');
    }
  };

  const handleDelete = async (enhancementId: string) => {
    const doDelete = async () => {
      try {
        await deleteEnhancement.mutateAsync({ noteId, enhancementId });
      } catch (err: any) {
        alert(err.message || 'Failed to delete enhancement');
      }
    };

    if (typeof Alert !== 'undefined') {
      Alert.alert('Confirm Delete', 'Are you sure you want to delete this AI enhancement?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: doDelete },
      ]);
    } else {
      doDelete();
    }
  };

  const activeEnhancement = enhancements?.find((e) => e.enhancement_type === selectedType);

  const enhancementTypes = [
    { label: 'Improved', value: 'improved' },
    { label: 'Professional', value: 'professional' },
    { label: 'Blog', value: 'blog' },
    { label: 'Report', value: 'executive_report' },
    { label: 'Email', value: 'email' },
    { label: 'Project Update', value: 'project_update' },
  ] as const;

  const providers = ['openai', 'anthropic', 'gemini'] as const;

  const renderActiveContent = () => {
    if (!activeEnhancement) return null;

    const data = activeEnhancement.structured_data;

    switch (selectedType) {
      case 'improved':
      case 'professional':
        return (
          <View style={{ marginTop: 8 }}>
            <Text variant="titleMedium" style={{ fontWeight: '700', marginBottom: 8 }}>
              {data.title || 'Enhanced Note'}
            </Text>
            <Text variant="bodyMedium" style={{ lineHeight: 22, opacity: 0.9 }}>
              {data.content}
            </Text>
          </View>
        );
      case 'blog':
        return (
          <View style={{ marginTop: 8 }}>
            <Text variant="titleMedium" style={{ fontWeight: '700', marginBottom: 12 }}>
              {data.title || 'Blog Post Draft'}
            </Text>
            {data.sections?.map((sec: any, idx: number) => (
              <View key={idx} style={{ marginBottom: 12 }}>
                <Text variant="titleSmall" style={{ fontWeight: '600', marginBottom: 4 }}>
                  {sec.heading}
                </Text>
                <Text variant="bodyMedium" style={{ lineHeight: 20, opacity: 0.9 }}>
                  {sec.content}
                </Text>
              </View>
            ))}
            {data.conclusion ? (
              <View style={{ marginTop: 8, paddingTop: 8, borderTopWidth: 1, borderColor: 'rgba(255,255,255,0.1)' }}>
                <Text variant="titleSmall" style={{ fontWeight: '600', marginBottom: 4 }}>
                  Conclusion
                </Text>
                <Text variant="bodyMedium" style={{ lineHeight: 20, opacity: 0.9 }}>
                  {data.conclusion}
                </Text>
              </View>
            ) : null}
          </View>
        );
      case 'executive_report':
        return (
          <View style={{ marginTop: 8, gap: 12 }}>
            <Text variant="titleMedium" style={{ fontWeight: '700' }}>
              {data.title || 'Executive Report'}
            </Text>
            {data.executive_summary ? (
              <Card style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: 12 }}>
                <Text variant="titleSmall" style={{ fontWeight: '600', marginBottom: 4 }}>
                  Executive Summary
                </Text>
                <Text variant="bodyMedium" style={{ opacity: 0.9 }}>{data.executive_summary}</Text>
              </Card>
            ) : null}
            {data.background ? (
              <Card style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: 12 }}>
                <Text variant="titleSmall" style={{ fontWeight: '600', marginBottom: 4 }}>
                  Background
                </Text>
                <Text variant="bodyMedium" style={{ opacity: 0.9 }}>{data.background}</Text>
              </Card>
            ) : null}
            {data.key_findings && data.key_findings.length > 0 ? (
              <Card style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: 12 }}>
                <Text variant="titleSmall" style={{ fontWeight: '600', marginBottom: 4 }}>
                  Key Findings
                </Text>
                {data.key_findings.map((item: string, idx: number) => (
                  <Text key={idx} variant="bodyMedium" style={{ opacity: 0.9, marginVertical: 2 }}>
                    • {item}
                  </Text>
                ))}
              </Card>
            ) : null}
            {data.recommendations && data.recommendations.length > 0 ? (
              <Card style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: 12 }}>
                <Text variant="titleSmall" style={{ fontWeight: '600', marginBottom: 4 }}>
                  Recommendations
                </Text>
                {data.recommendations.map((item: string, idx: number) => (
                  <Text key={idx} variant="bodyMedium" style={{ opacity: 0.9, marginVertical: 2 }}>
                    • {item}
                  </Text>
                ))}
              </Card>
            ) : null}
          </View>
        );
      case 'email':
        return (
          <View style={{ marginTop: 8, gap: 8 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text variant="titleMedium" style={{ fontWeight: '700' }}>
                Email Draft
              </Text>
            </View>
            <Card style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: 12, gap: 8 }}>
              <Text variant="bodyMedium" style={{ fontWeight: '600' }}>
                Subject: {data.subject}
              </Text>
              <Divider style={{ marginVertical: 4 }} />
              <Text variant="bodyMedium">{data.greeting}</Text>
              <Text variant="bodyMedium" style={{ marginVertical: 4 }}>{data.body}</Text>
              <Text variant="bodyMedium">{data.signature_placeholder}</Text>
            </Card>
          </View>
        );
      case 'project_update':
        const getBadgeStyle = (color: string) => {
          switch (color) {
            case 'green':
              return { bg: '#10B981', text: '#FFFFFF' };
            case 'yellow':
              return { bg: '#F59E0B', text: '#000000' };
            case 'red':
              return { bg: '#EF4444', text: '#FFFFFF' };
            default:
              return { bg: '#6B7280', text: '#FFFFFF' };
          }
        };
        const badge = getBadgeStyle(data.status_color || 'green');
        return (
          <View style={{ marginTop: 8, gap: 12 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text variant="titleMedium" style={{ fontWeight: '700' }}>
                {data.project_name || 'Project Update'}
              </Text>
              <View style={{ backgroundColor: badge.bg, paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12 }}>
                <Text style={{ color: badge.text, fontWeight: '700', fontSize: 12, textTransform: 'uppercase' }}>
                  {data.status_color || 'green'}
                </Text>
              </View>
            </View>
            {data.milestones_completed && data.milestones_completed.length > 0 ? (
              <Card style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: 12 }}>
                <Text variant="titleSmall" style={{ fontWeight: '600', marginBottom: 4 }}>
                  Milestones Completed
                </Text>
                {data.milestones_completed.map((item: string, idx: number) => (
                  <Text key={idx} variant="bodyMedium" style={{ opacity: 0.9, marginVertical: 2 }}>
                    ✓ {item}
                  </Text>
                ))}
              </Card>
            ) : null}
            {data.current_blockers && data.current_blockers.length > 0 ? (
              <Card style={{ backgroundColor: 'rgba(239, 68, 68, 0.05)', borderColor: 'rgba(239, 68, 68, 0.2)', borderWidth: 1, padding: 12 }}>
                <Text variant="titleSmall" style={{ fontWeight: '600', color: '#EF4444', marginBottom: 4 }}>
                  Current Blockers
                </Text>
                {data.current_blockers.map((item: string, idx: number) => (
                  <Text key={idx} variant="bodyMedium" style={{ color: '#FCA5A5', marginVertical: 2 }}>
                    ⚠ {item}
                  </Text>
                ))}
              </Card>
            ) : null}
            {data.next_steps && data.next_steps.length > 0 ? (
              <Card style={{ backgroundColor: 'rgba(255, 255, 255, 0.02)', padding: 12 }}>
                <Text variant="titleSmall" style={{ fontWeight: '600', marginBottom: 4 }}>
                  Next Steps
                </Text>
                {data.next_steps.map((item: string, idx: number) => (
                  <Text key={idx} variant="bodyMedium" style={{ opacity: 0.9, marginVertical: 2 }}>
                    → {item}
                  </Text>
                ))}
              </Card>
            ) : null}
          </View>
        );
      default:
        return null;
    }
  };

  if (isLoading) {
    return (
      <View style={styles.mmCenter}>
        <ActivityIndicator size="small" color={theme.colors.primary} />
        <Text style={[styles.mmLoadingText, { color: theme.colors.secondary }]}>
          Loading AI enhancements...
        </Text>
      </View>
    );
  }

  if (generateEnhancement.isPending) {
    return (
      <View style={styles.mmCenter}>
        <ActivityIndicator size="large" color={theme.colors.primary} style={{ marginBottom: 12 }} />
        <Text variant="titleMedium" style={styles.mmGeneratingTitle}>
          ✨ Generating Enhancement...
        </Text>
        <Text style={[styles.mmLoadingText, { color: theme.colors.secondary }]}>
          Analyzing transcript and creating structured '{selectedType}' draft. Please wait...
        </Text>
      </View>
    );
  }

  return (
    <Card style={StyleSheet.flatten([styles.cardSpacing, { backgroundColor: theme.colors.elevation.level2 }])}>
      <Text variant="titleMedium" style={{ fontWeight: '700', marginBottom: 12 }}>
        ✨ AI Note Enhancements
      </Text>

      {/* Style Selector Pills */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {enhancementTypes.map((type) => {
            const hasDraft = enhancements?.some((e) => e.enhancement_type === type.value);
            const isSelected = selectedType === type.value;
            return (
              <TouchableOpacity
                key={type.value}
                onPress={() => setSelectedType(type.value)}
                style={{
                  paddingHorizontal: 12,
                  paddingVertical: 6,
                  borderRadius: 16,
                  backgroundColor: isSelected
                    ? theme.colors.primary
                    : 'rgba(255, 255, 255, 0.05)',
                  borderWidth: 1,
                  borderColor: isSelected
                    ? theme.colors.primary
                    : hasDraft
                    ? 'rgba(255, 255, 255, 0.2)'
                    : 'transparent',
                }}
              >
                <Text
                  style={{
                    color: isSelected
                      ? '#FFFFFF'
                      : hasDraft
                      ? theme.colors.primary
                      : theme.colors.secondary,
                    fontWeight: isSelected || hasDraft ? '700' : '400',
                    fontSize: 12,
                  }}
                >
                  {type.label} {hasDraft ? '✓' : ''}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </ScrollView>

      {/* Content Area */}
      {activeEnhancement ? (
        <View style={{ gap: 12 }}>
          {renderActiveContent()}

          <Divider style={{ marginVertical: 8 }} />

          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text variant="bodySmall" style={{ color: theme.colors.secondary, opacity: 0.6 }}>
              {activeEnhancement.provider} ({activeEnhancement.model})
            </Text>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <TouchableOpacity
                onPress={() => handleDelete(activeEnhancement.id)}
                style={{
                  paddingHorizontal: 10,
                  paddingVertical: 6,
                  borderRadius: 4,
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                }}
              >
                <Text style={{ color: '#EF4444', fontSize: 11, fontWeight: '700' }}>Delete</Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={handleGenerate}
                disabled={!isOnline}
                style={{
                  paddingHorizontal: 10,
                  paddingVertical: 6,
                  borderRadius: 4,
                  backgroundColor: isOnline ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.02)',
                }}
              >
                <Text style={{ color: isOnline ? theme.colors.primary : theme.colors.secondary, fontSize: 11, fontWeight: '700' }}>
                  Regenerate
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      ) : (
        <View style={{ alignItems: 'center', paddingVertical: 12 }}>
          <Text variant="titleSmall" style={{ fontWeight: '600', marginBottom: 4 }}>
            No Draft Generated
          </Text>
          <Text
            variant="bodyMedium"
            style={{
              textAlign: 'center',
              color: theme.colors.secondary,
              marginBottom: 12,
              fontSize: 13,
            }}
          >
            Generate a {selectedType.replace('_', ' ')} draft of this note using AI.
          </Text>

          {/* Provider Selection Pills */}
          <View style={{ flexDirection: 'row', gap: 6, marginBottom: 16 }}>
            {providers.map((p) => {
              const isSelected = selectedProvider === p;
              return (
                <TouchableOpacity
                  key={p}
                  onPress={() => setSelectedProvider(p)}
                  style={{
                    paddingHorizontal: 10,
                    paddingVertical: 4,
                    borderRadius: 12,
                    backgroundColor: isSelected
                      ? 'rgba(255,255,255,0.1)'
                      : 'rgba(255, 255, 255, 0.02)',
                    borderWidth: 1,
                    borderColor: isSelected ? theme.colors.primary : 'transparent',
                  }}
                >
                  <Text
                    style={{
                      color: isSelected ? theme.colors.primary : theme.colors.secondary,
                      fontSize: 11,
                      fontWeight: isSelected ? '700' : '400',
                      textTransform: 'capitalize',
                    }}
                  >
                    {p}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {transcription ? (
            <Button
              title={`✨ Generate ${selectedType.replace('_', ' ')}`}
              onPress={handleGenerate}
              disabled={!isOnline}
            />
          ) : (
            <Text style={{ color: theme.colors.error, fontSize: 13, fontWeight: '600' }}>
              No transcript available to enhance.
            </Text>
          )}

          {!isOnline && (
            <Text style={{ color: '#F59E0B', fontSize: 12, marginTop: 8 }}>
              ⚠️ Online connection required to generate.
            </Text>
          )}
        </View>
      )}
    </Card>
  );
}

interface MeetingMinutesViewProps {
  noteId: string;
  transcription?: string;
  isOnline: boolean;
}

function MeetingMinutesView({ noteId, transcription, isOnline }: MeetingMinutesViewProps) {
  const theme = useTheme();
  const { data: minutes, isLoading } = useMeetingMinutesQuery(noteId);
  const generateMinutes = useGenerateMinutesMutation();
  const deleteMinutes = useDeleteMinutesMutation();

  const handleGenerate = async () => {
    try {
      await generateMinutes.mutateAsync({ noteId });
    } catch (err: any) {
      alert(err.message || 'Failed to generate meeting minutes');
    }
  };

  const handleDelete = () => {
    const doDelete = async () => {
      try {
        await deleteMinutes.mutateAsync(noteId);
      } catch (err: any) {
        alert(err.message || 'Failed to delete meeting minutes');
      }
    };

    if (typeof Alert !== 'undefined') {
      Alert.alert('Confirm Delete', 'Are you sure you want to delete these meeting minutes?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: doDelete },
      ]);
    } else {
      doDelete();
    }
  };

  if (isLoading) {
    return (
      <View style={styles.mmCenter}>
        <ActivityIndicator size="small" color={theme.colors.primary} />
        <Text style={[styles.mmLoadingText, { color: theme.colors.secondary }]}>
          Loading meeting minutes...
        </Text>
      </View>
    );
  }

  if (generateMinutes.isPending) {
    return (
      <View style={styles.mmCenter}>
        <ActivityIndicator size="large" color={theme.colors.primary} style={{ marginBottom: 12 }} />
        <Text variant="titleMedium" style={styles.mmGeneratingTitle}>
          ✨ Creating Minutes...
        </Text>
        <Text style={[styles.mmLoadingText, { color: theme.colors.secondary }]}>
          Analyzing transcript and compiling overview, agenda, discussions, decisions, and action
          items. Please wait...
        </Text>
      </View>
    );
  }

  if (!minutes) {
    return (
      <Card
        style={StyleSheet.flatten([
          styles.mmEmptyCard,
          { backgroundColor: theme.colors.elevation.level2 },
        ])}
      >
        <View style={{ alignItems: 'center' }}>
          <Text variant="titleMedium" style={styles.mmEmptyTitle}>
            No Meeting Minutes Found
          </Text>
          <Text
            variant="bodyMedium"
            style={[styles.mmEmptyDesc, { color: theme.colors.secondary }]}
          >
            You can generate structured meeting minutes including agenda, key discussion points,
            decisions, risks, and action items with owners and due dates directly from the
            transcription.
          </Text>
          {transcription ? (
            <Button
              title="✨ Generate Meeting Minutes"
              onPress={handleGenerate}
              disabled={!isOnline}
            />
          ) : (
            <Text style={[styles.mmErrorText, { color: theme.colors.error }]}>
              No transcript available. Please wait for transcription to finish.
            </Text>
          )}
          {!isOnline && (
            <Text style={[styles.mmWarningText, { color: '#F59E0B' }]}>
              ⚠️ You must be online to generate meeting minutes.
            </Text>
          )}
        </View>
      </Card>
    );
  }

  return (
    <View style={styles.mmContainer}>
      {/* Overview */}
      <Card
        style={StyleSheet.flatten([
          styles.mmSectionCard,
          { backgroundColor: theme.colors.elevation.level2 },
        ])}
      >
        <Text variant="titleMedium" style={styles.mmSectionTitle}>
          📋 Meeting Overview
        </Text>
        <Text variant="bodyMedium" style={{ lineHeight: 22, opacity: 0.9 }}>
          {minutes.overview}
        </Text>
        <Text variant="bodySmall" style={[styles.mmMetaText, { color: theme.colors.secondary }]}>
          Generated using {minutes.provider} ({minutes.model})
        </Text>
      </Card>

      {/* Agenda */}
      {minutes.agenda && minutes.agenda.length > 0 && (
        <Card
          style={StyleSheet.flatten([
            styles.mmSectionCard,
            { backgroundColor: theme.colors.elevation.level2 },
          ])}
        >
          <Text variant="titleMedium" style={styles.mmSectionTitle}>
            🎯 Agenda
          </Text>
          <View style={styles.mmAgendaContainer}>
            {minutes.agenda.map((item, index) => (
              <View key={index} style={styles.mmAgendaItem}>
                <Text style={[styles.mmBullet, { color: theme.colors.primary }]}>•</Text>
                <Text variant="bodyMedium" style={{ flex: 1 }}>
                  {item}
                </Text>
              </View>
            ))}
          </View>
        </Card>
      )}

      {/* Discussion Points */}
      {minutes.discussion_points && minutes.discussion_points.length > 0 && (
        <Card
          style={StyleSheet.flatten([
            styles.mmSectionCard,
            { backgroundColor: theme.colors.elevation.level2 },
          ])}
        >
          <Text variant="titleMedium" style={styles.mmSectionTitle}>
            💬 Key Discussion Points
          </Text>
          {minutes.discussion_points.map((point, index) => (
            <View
              key={index}
              style={[styles.mmDiscussionPoint, { borderBottomColor: theme.colors.outlineVariant }]}
            >
              <Text variant="titleSmall" style={{ fontWeight: '700', marginBottom: 4 }}>
                {point.topic}
              </Text>
              <Text variant="bodyMedium" style={{ opacity: 0.85, lineHeight: 20 }}>
                {point.summary}
              </Text>
            </View>
          ))}
        </Card>
      )}

      {/* Decisions */}
      {minutes.decisions && minutes.decisions.length > 0 && (
        <Card
          style={StyleSheet.flatten([
            styles.mmSectionCard,
            { backgroundColor: theme.colors.elevation.level2 },
          ])}
        >
          <Text variant="titleMedium" style={styles.mmSectionTitle}>
            ✅ Decisions Made
          </Text>
          <View style={styles.mmAgendaContainer}>
            {minutes.decisions.map((decision, index) => (
              <View key={index} style={styles.mmAgendaItem}>
                <Text style={[styles.mmBullet, { color: '#10B981' }]}>✔</Text>
                <Text variant="bodyMedium" style={{ flex: 1, fontWeight: '600' }}>
                  {decision}
                </Text>
              </View>
            ))}
          </View>
        </Card>
      )}

      {/* Risks */}
      {minutes.risks && minutes.risks.length > 0 && (
        <Card
          style={StyleSheet.flatten([
            styles.mmSectionCard,
            { backgroundColor: 'rgba(239, 68, 68, 0.05)', borderColor: '#EF4444', borderWidth: 1 },
          ])}
        >
          <Text variant="titleMedium" style={[styles.mmSectionTitle, { color: '#EF4444' }]}>
            ⚠️ Risks & Concerns
          </Text>
          <View style={styles.mmAgendaContainer}>
            {minutes.risks.map((risk, index) => (
              <View key={index} style={styles.mmAgendaItem}>
                <Text style={[styles.mmBullet, { color: '#EF4444' }]}>⚠</Text>
                <Text variant="bodyMedium" style={{ flex: 1, color: '#EF4444', fontWeight: '500' }}>
                  {risk}
                </Text>
              </View>
            ))}
          </View>
        </Card>
      )}

      {/* Action Items */}
      {minutes.action_items && minutes.action_items.length > 0 && (
        <Card
          style={StyleSheet.flatten([
            styles.mmSectionCard,
            { backgroundColor: theme.colors.elevation.level2 },
          ])}
        >
          <Text variant="titleMedium" style={styles.mmSectionTitle}>
            🏃‍♂️ Action Items
          </Text>
          {minutes.action_items.map((item, index) => (
            <Card
              key={index}
              style={StyleSheet.flatten([
                styles.mmActionCard,
                { backgroundColor: theme.colors.elevation.level3 },
              ])}
            >
              <Text variant="titleSmall" style={{ fontWeight: '700', marginBottom: 6 }}>
                {item.task}
              </Text>
              <View style={styles.mmActionMetaRow}>
                <View style={styles.mmActionMeta}>
                  <Text variant="bodySmall" style={{ color: theme.colors.secondary }}>
                    Owner:
                  </Text>
                  <Text variant="bodyMedium" style={{ fontWeight: '600' }}>
                    {item.owner || 'Unassigned'}
                  </Text>
                </View>
                <View style={styles.mmActionMeta}>
                  <Text variant="bodySmall" style={{ color: theme.colors.secondary }}>
                    Due Date:
                  </Text>
                  <Text variant="bodyMedium" style={{ fontWeight: '600' }}>
                    {item.due_date || 'TBD'}
                  </Text>
                </View>
              </View>
            </Card>
          ))}
        </Card>
      )}

      {/* Delete / Regenerate */}
      <Button
        title="Delete Meeting Minutes"
        variant="danger"
        onPress={handleDelete}
        style={{ marginTop: 8 }}
      />
    </View>
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
  // Meeting Minutes Styles
  mmCenter: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  mmLoadingText: {
    marginTop: 12,
    fontSize: 14,
    textAlign: 'center',
  },
  mmGeneratingTitle: {
    fontSize: 16,
    fontWeight: '700',
    textAlign: 'center',
  },
  mmEmptyCard: {
    borderRadius: 12,
    marginVertical: 8,
  },
  mmEmptyTitle: {
    fontWeight: '700',
    marginBottom: 8,
    textAlign: 'center',
  },
  mmEmptyDesc: {
    textAlign: 'center',
    marginBottom: 16,
    opacity: 0.8,
    lineHeight: 20,
  },
  mmErrorText: {
    fontWeight: '600',
    textAlign: 'center',
    marginTop: 8,
  },
  mmWarningText: {
    fontWeight: '600',
    marginTop: 12,
    textAlign: 'center',
  },
  mmContainer: {
    marginTop: 8,
    gap: 16,
  },
  mmSectionCard: {
    borderRadius: 12,
    marginVertical: 4,
  },
  mmSectionTitle: {
    fontWeight: '800',
    marginBottom: 12,
    fontSize: 16,
  },
  mmMetaText: {
    fontSize: 11,
    marginTop: 12,
    opacity: 0.6,
  },
  mmAgendaContainer: {
    gap: 8,
  },
  mmAgendaItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
  },
  mmBullet: {
    fontSize: 16,
    fontWeight: '700',
    width: 16,
  },
  mmDiscussionPoint: {
    borderBottomWidth: 1,
    paddingVertical: 12,
    gap: 4,
  },
  mmActionCard: {
    borderRadius: 8,
    marginVertical: 4,
  },
  mmActionMetaRow: {
    flexDirection: 'row',
    gap: 24,
    marginTop: 4,
  },
  mmActionMeta: {
    flex: 1,
    gap: 2,
  },
  searchCardContainer: {
    marginBottom: 12,
    position: 'relative',
  },
  relevanceBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
    backgroundColor: 'white',
  },
  semanticBadge: {
    backgroundColor: 'rgba(155, 89, 182, 0.15)',
    borderColor: '#9b59b6',
  },
  ftsBadge: {
    backgroundColor: 'rgba(52, 152, 219, 0.15)',
    borderColor: '#3498db',
  },
  hybridBadge: {
    backgroundColor: 'rgba(46, 204, 113, 0.15)',
    borderColor: '#2ecc71',
  },
  badgeText: {
    fontSize: 9,
    fontWeight: 'bold',
    color: '#2c3e50',
  },
  searchTypeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 8,
  },
  chipButton: {
    flex: 1,
    paddingVertical: 4,
    borderRadius: 8,
    minWidth: 0,
  },
});
