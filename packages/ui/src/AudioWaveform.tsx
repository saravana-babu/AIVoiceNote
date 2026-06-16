import React, { useEffect, useRef } from 'react';
import { StyleSheet, View, Animated, ViewStyle } from 'react-native';
import { useTheme } from 'react-native-paper';

export interface AudioWaveformProps {
  isPlaying?: boolean;
  isRecording?: boolean;
  progress?: number; // 0 to 1
  style?: ViewStyle;
  barCount?: number;
  meteringHistory?: number[];
}

export const AudioWaveform: React.FC<AudioWaveformProps> = ({
  isPlaying = false,
  isRecording = false,
  progress = 0,
  style,
  barCount = 28,
  meteringHistory,
}) => {
  const theme = useTheme();

  // Generate stable mock heights for the waveform shape (bell curve-ish)
  const baseHeights = useRef<number[]>(
    Array.from({ length: barCount }, (_, i) => {
      const x = i / (barCount - 1);
      // Bell curve + some noise
      const bell = Math.exp(-Math.pow(x - 0.5, 2) / 0.08);
      const noise = 0.15 + 0.7 * Math.sin(x * Math.PI * 4.5);
      return Math.max(10, Math.round(bell * (30 + noise * 15)));
    }),
  ).current;

  // Calculate live heights if meteringHistory is supplied
  const displayHeights = React.useMemo(() => {
    if (meteringHistory && meteringHistory.length > 0) {
      const historyLength = meteringHistory.length;
      return Array.from({ length: barCount }, (_, i) => {
        const historyIndex = historyLength - barCount + i;
        if (historyIndex >= 0) {
          const val = meteringHistory[historyIndex];
          // val is normalized 0.0 to 1.0. Map it to height range 4 to 50
          return Math.max(4, Math.round(val * 46));
        }
        return 4; // minimum height
      });
    }
    return baseHeights;
  }, [meteringHistory, barCount, baseHeights]);

  // Animation values for each bar (for live recording visualizer fallback)
  const animatedScales = useRef(
    Array.from({ length: barCount }, () => new Animated.Value(1)),
  ).current;

  useEffect(() => {
    let animLoop: Animated.CompositeAnimation | null = null;

    // Only run mock pulsating animation if recording and no live metering data is provided
    if (isRecording && (!meteringHistory || meteringHistory.length === 0)) {
      // Create a pulsating/dancing wave animation
      const anims = animatedScales.map((val) =>
        Animated.loop(
          Animated.sequence([
            Animated.timing(val, {
              toValue: 0.3 + Math.random() * 1.4,
              duration: 150 + Math.random() * 200,
              useNativeDriver: true,
            }),
            Animated.timing(val, {
              toValue: 0.5 + Math.random() * 0.7,
              duration: 150 + Math.random() * 200,
              useNativeDriver: true,
            }),
          ]),
        ),
      );

      animLoop = Animated.parallel(anims);
      animLoop.start();
    } else {
      // Reset animations smoothly
      animatedScales.forEach((val) => {
        Animated.spring(val, {
          toValue: 1,
          friction: 6,
          useNativeDriver: true,
        }).start();
      });
    }

    return () => {
      animLoop?.stop();
    };
  }, [isRecording, animatedScales, meteringHistory]);

  return (
    <View
      style={[styles.container, style]}
      accessibilityLabel={
        isRecording
          ? 'Active audio waveform visualizer'
          : isPlaying
            ? `Audio waveform playing, progress ${Math.round(progress * 100)} percent`
            : 'Audio waveform'
      }
      accessibilityRole="image"
    >
      <View style={styles.waveRow}>
        {displayHeights.map((height, index) => {
          // Calculate if this bar has been played past
          const isPlayed = progress > index / barCount;
          const barColor = isRecording
            ? theme.colors.error
            : isPlayed
              ? theme.colors.primary
              : theme.colors.outline;

          const animatedStyle = {
            transform: [{ scaleY: animatedScales[index] }],
          };

          const useAnim = isRecording && (!meteringHistory || meteringHistory.length === 0);

          return (
            <Animated.View
              key={index}
              style={[
                styles.bar,
                {
                  height,
                  backgroundColor: barColor,
                },
                useAnim && animatedStyle,
              ]}
            />
          );
        })}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    height: 60,
    justifyContent: 'center',
    width: '100%',
    paddingVertical: 8,
  },
  waveRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
    height: '100%',
  },
  bar: {
    width: 3,
    minHeight: 4,
    borderRadius: 2,
    marginHorizontal: 1,
  },
});
