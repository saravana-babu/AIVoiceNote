import React, { useState } from 'react';
import { StyleSheet, View, SafeAreaView, ScrollView, useWindowDimensions } from 'react-native';
import { PaperProvider, Text, Divider, Switch, useTheme } from 'react-native-paper';
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

export default function App() {
  const [isDarkMode, setIsDarkMode] = useState(true);
  const theme = isDarkMode ? customDarkTheme : customLightTheme;

  return (
    <PaperProvider theme={theme}>
      <MainAppContent isDarkMode={isDarkMode} setIsDarkMode={setIsDarkMode} />
    </PaperProvider>
  );
}

interface MainContentProps {
  isDarkMode: boolean;
  setIsDarkMode: (val: boolean) => void;
}

function MainAppContent({ isDarkMode, setIsDarkMode }: MainContentProps) {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;

  // States for interactive showcase elements
  const [inputText, setInputText] = useState('');
  const [searchVal, setSearchVal] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isPlayingNote, setIsPlayingNote] = useState(false);
  const [playProgress, setPlayProgress] = useState(0.4);

  // Modal, Dialog, Sheet visibility states
  const [modalVisible, setModalVisible] = useState(false);
  const [dialogVisible, setDialogVisible] = useState(false);
  const [sheetVisible, setSheetVisible] = useState(false);

  // Mock Voice Note data
  const sampleNote: VoiceNote = {
    id: 'sample-1',
    title: 'VoiceMind AI Design System Notes',
    createdAt: new Date().toISOString(),
    durationSec: 134,
    filePath: 'file:///mock-note.m4a',
    status: 'completed',
    transcription:
      'We are showcasing the new design system components using React Native Paper. All components support light and dark mode, accessibility, and desktop side sheets.',
    tags: ['design-system', 'voice-mind', 'expo', 'monorepo'],
  };

  // Simulate progress when playing
  React.useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlayingNote) {
      interval = setInterval(() => {
        setPlayProgress((prev) => (prev >= 1 ? 0 : prev + 0.05));
      }, 500);
    }
    return () => clearInterval(interval);
  }, [isPlayingNote]);

  return (
    <SafeAreaView style={[styles.safeArea, { backgroundColor: theme.colors.background }]}>
      {/* Top Header bar with Theme Toggle */}
      <View style={[styles.header, { borderBottomColor: theme.colors.outline }]}>
        <View>
          <Text variant="headlineMedium" style={styles.title}>
            VoiceMind AI
          </Text>
          <Text variant="bodyMedium" style={{ color: theme.colors.secondary }}>
            Design System Catalog
          </Text>
        </View>
        <View style={styles.toggleRow}>
          <Text variant="labelLarge" style={styles.toggleLabel}>
            {isDarkMode ? '🌙 Dark Mode' : '☀️ Light Mode'}
          </Text>
          <Switch value={isDarkMode} onValueChange={setIsDarkMode} />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContainer}>
        {/* Responsive Grid Setup */}
        <View style={[styles.grid, isDesktop ? styles.desktopGrid : styles.mobileGrid]}>
          {/* Column 1: Buttons & Inputs */}
          <View style={[styles.column, isDesktop ? styles.desktopColumn : null]}>
            <Text variant="titleLarge" style={styles.sectionHeader}>
              Buttons & Inputs
            </Text>

            <Card style={styles.cardSpacing}>
              <Text variant="titleMedium" style={styles.cardHeader}>
                Button Variants
              </Text>
              <View style={styles.rowGap}>
                <Button title="Primary Button" onPress={() => alert('Primary pressed')} />
                <Button
                  title="Secondary Button"
                  onPress={() => alert('Secondary pressed')}
                  variant="secondary"
                />
                <Button
                  title="Danger Button"
                  onPress={() => alert('Danger pressed')}
                  variant="danger"
                />
                <Button title="Loading Button" onPress={() => {}} loading />
              </View>
            </Card>

            <Card style={styles.cardSpacing}>
              <Text variant="titleMedium" style={styles.cardHeader}>
                Text Inputs & Search
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
                style={styles.fieldSpacing}
              />
              <Input
                label="Secure Input"
                value={inputText}
                onChangeText={setInputText}
                secureTextEntry
                placeholder="Enter password"
              />
            </Card>
          </View>

          {/* Column 2: Audio Primitives & Overlays */}
          <View style={[styles.column, isDesktop ? styles.desktopColumn : null]}>
            <Text variant="titleLarge" style={styles.sectionHeader}>
              Audio & Cards
            </Text>

            <Card style={styles.cardSpacing}>
              <Text variant="titleMedium" style={styles.cardHeader}>
                Recording Trigger & Waveforms
              </Text>
              <View style={styles.centerRow}>
                <RecordingButton
                  isRecording={isRecording}
                  onPress={() => setIsRecording(!isRecording)}
                />
                <Text style={styles.recordingLabel}>
                  {isRecording ? 'Recording active... (pulsating)' : 'Tap circle to record'}
                </Text>
              </View>
              <Divider style={styles.divider} />
              <Text variant="bodySmall" style={styles.subtext}>
                Dynamic Waveform (Active during recording)
              </Text>
              <AudioWaveform isRecording={isRecording} />
            </Card>

            <Card style={styles.cardSpacing}>
              <Text variant="titleMedium" style={styles.cardHeader}>
                Note Card Component
              </Text>
              <NoteCard
                note={sampleNote}
                isPlaying={isPlayingNote}
                playbackProgress={playProgress}
                onPlayPause={() => setIsPlayingNote(!isPlayingNote)}
                onDelete={() => alert('Delete pressed')}
                onTagPress={(tag) => alert(`Selected tag: #${tag}`)}
              />
            </Card>

            <Card style={styles.cardSpacing}>
              <Text variant="titleMedium" style={styles.cardHeader}>
                Modals, Sheets & Dialogs
              </Text>
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
  safeArea: {
    flex: 1,
  },
  header: {
    paddingHorizontal: 24,
    paddingVertical: 16,
    borderBottomWidth: 1,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {
    fontWeight: '800',
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  toggleLabel: {
    marginRight: 4,
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
});
