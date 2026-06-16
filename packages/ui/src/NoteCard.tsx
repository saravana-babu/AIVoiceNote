import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Card, Text, Chip, IconButton, useTheme } from 'react-native-paper';
import { VoiceNote } from '@voicemind/shared';
import { AudioWaveform } from './AudioWaveform.js';

export interface NoteCardProps {
  note: VoiceNote;
  isPlaying?: boolean;
  playbackProgress?: number;
  onPlayPause?: () => void;
  onPress?: () => void;
  onDelete?: () => void;
  onTagPress?: (tag: string) => void;
}

export const NoteCard: React.FC<NoteCardProps> = ({
  note,
  isPlaying = false,
  playbackProgress = 0,
  onPlayPause,
  onPress,
  onDelete,
  onTagPress,
}) => {
  const theme = useTheme();

  // Format duration (e.g. 72s -> "1:12")
  const formatDuration = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const remainder = Math.floor(sec % 60);
    return `${mins}:${remainder.toString().padStart(2, '0')}`;
  };

  // Format date (e.g. "2026-06-16T16:24:50Z" -> "Jun 16, 2026")
  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  const isTranscribing = note.status === 'transcribing';

  return (
    <Card
      mode="contained"
      onPress={onPress}
      style={[
        styles.card,
        { backgroundColor: theme.colors.elevation.level1 },
        isPlaying && { borderColor: theme.colors.primary, borderWidth: 1.5 },
      ]}
      accessibilityLabel={`Voice note: ${note.title}. Duration ${formatDuration(note.durationSec)}`}
    >
      <Card.Content>
        {/* Top row: Title & Menu */}
        <View style={styles.headerRow}>
          <View style={styles.titleContainer}>
            <Text variant="titleMedium" style={styles.title} numberOfLines={1}>
              {note.title || 'Untitled Recording'}
            </Text>
            <Text variant="bodySmall" style={{ color: theme.colors.secondary }}>
              {formatDate(note.createdAt)} • {formatDuration(note.durationSec)}
            </Text>
          </View>
          <View style={styles.actions}>
            {onDelete && (
              <IconButton
                icon="delete-outline"
                size={20}
                iconColor={theme.colors.outline}
                onPress={onDelete}
                accessibilityLabel="Delete voice note"
              />
            )}
          </View>
        </View>

        {/* Middle row: Transcription excerpt or spinner */}
        <View style={styles.contentContainer}>
          {isTranscribing ? (
            <View style={styles.transcribingContainer}>
              <Text
                variant="bodyMedium"
                style={[styles.transcribingText, { color: theme.colors.primary }]}
              >
                ✨ Transcribing audio...
              </Text>
            </View>
          ) : note.transcription ? (
            <Text variant="bodyMedium" style={styles.transcription} numberOfLines={2}>
              {note.transcription}
            </Text>
          ) : null}
        </View>

        {/* Audio Waveform (shown when expanded/playing) */}
        {isPlaying && (
          <AudioWaveform
            isPlaying={isPlaying}
            progress={playbackProgress}
            style={styles.waveform}
          />
        )}

        {/* Bottom row: Play/Pause button & Tags */}
        <View style={styles.footerRow}>
          {onPlayPause && note.status === 'completed' && (
            <IconButton
              icon={isPlaying ? 'pause-circle' : 'play-circle'}
              size={32}
              iconColor={theme.colors.primary}
              onPress={onPlayPause}
              style={styles.playButton}
              accessibilityLabel={isPlaying ? 'Pause playback' : 'Play recording'}
            />
          )}

          <View style={[styles.tagsContainer, onPlayPause ? null : { marginLeft: 0 }]}>
            {note.tags.map((tag) => (
              <Chip
                key={tag}
                style={styles.tagChip}
                textStyle={styles.tagText}
                onPress={onTagPress ? () => onTagPress(tag) : undefined}
                compact
              >
                #{tag}
              </Chip>
            ))}
          </View>
        </View>
      </Card.Content>
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    marginVertical: 6,
    borderWidth: 1.5,
    borderColor: 'transparent',
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  titleContainer: {
    flex: 1,
  },
  title: {
    fontWeight: '700',
  },
  actions: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: -8,
    marginTop: -8,
  },
  contentContainer: {
    marginVertical: 10,
  },
  transcription: {
    lineHeight: 20,
    opacity: 0.8,
  },
  transcribingContainer: {
    paddingVertical: 4,
  },
  transcribingText: {
    fontWeight: '600',
  },
  waveform: {
    marginVertical: 8,
  },
  footerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 8,
  },
  playButton: {
    margin: 0,
    marginLeft: -10,
  },
  tagsContainer: {
    flex: 1,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    justifyContent: 'flex-end',
    marginLeft: 10,
  },
  tagChip: {
    borderRadius: 8,
    height: 24,
    justifyContent: 'center',
    backgroundColor: 'rgba(99, 102, 241, 0.08)',
  },
  tagText: {
    fontSize: 11,
    marginHorizontal: 4,
  },
});
