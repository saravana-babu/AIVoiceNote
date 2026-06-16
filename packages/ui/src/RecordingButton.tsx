import React, { useEffect, useRef } from 'react';
import { StyleSheet, View, Animated, TouchableOpacity } from 'react-native';
import { useTheme } from 'react-native-paper';

export interface RecordingButtonProps {
  isRecording: boolean;
  onPress: () => void;
  size?: number;
}

export const RecordingButton: React.FC<RecordingButtonProps> = ({
  isRecording,
  onPress,
  size = 72,
}) => {
  const theme = useTheme();
  const scaleValue = useRef(new Animated.Value(1)).current;
  const pulseValue = useRef(new Animated.Value(1)).current;
  const opacityValue = useRef(new Animated.Value(0.4)).current;

  useEffect(() => {
    let scaleAnim: Animated.CompositeAnimation | null = null;
    let pulseAnim: Animated.CompositeAnimation | null = null;

    if (isRecording) {
      // Small scale down for the center button
      scaleAnim = Animated.spring(scaleValue, {
        toValue: 0.9,
        friction: 4,
        useNativeDriver: true,
      });

      // Continuous pulsating for the outer ring
      pulseAnim = Animated.loop(
        Animated.parallel([
          Animated.timing(pulseValue, {
            toValue: 1.6,
            duration: 1200,
            useNativeDriver: true,
          }),
          Animated.timing(opacityValue, {
            toValue: 0,
            duration: 1200,
            useNativeDriver: true,
          }),
        ]),
      );

      scaleAnim.start();
      pulseAnim.start();
    } else {
      // Reset
      scaleAnim = Animated.spring(scaleValue, {
        toValue: 1,
        friction: 4,
        useNativeDriver: true,
      });

      pulseValue.setValue(1);
      opacityValue.setValue(0.4);

      scaleAnim.start();
    }

    return () => {
      scaleAnim?.stop();
      pulseAnim?.stop();
    };
  }, [isRecording, scaleValue, pulseValue, opacityValue]);

  const buttonSize = size;
  const innerSize = buttonSize * 0.8;
  const recordIconSize = isRecording ? innerSize * 0.4 : innerSize * 0.5;

  return (
    <View style={[styles.container, { width: buttonSize * 1.8, height: buttonSize * 1.8 }]}>
      {/* Pulsating Ring (Only when recording) */}
      {isRecording && (
        <Animated.View
          style={[
            styles.pulseRing,
            {
              width: buttonSize,
              height: buttonSize,
              borderRadius: buttonSize / 2,
              backgroundColor: theme.colors.error,
              transform: [{ scale: pulseValue }],
              opacity: opacityValue,
            },
          ]}
        />
      )}

      {/* Button border ring */}
      <View
        style={[
          styles.borderRing,
          {
            width: buttonSize,
            height: buttonSize,
            borderRadius: buttonSize / 2,
            borderColor: isRecording ? theme.colors.error : theme.colors.primary,
          },
        ]}
      >
        <TouchableOpacity
          onPress={onPress}
          activeOpacity={0.8}
          accessibilityLabel={
            isRecording ? 'Stop recording voice note' : 'Start recording voice note'
          }
          accessibilityRole="button"
          style={styles.touchArea}
        >
          {/* Main button circle */}
          <Animated.View
            style={[
              styles.buttonCircle,
              {
                width: innerSize,
                height: innerSize,
                borderRadius: innerSize / 2,
                backgroundColor: theme.colors.surface,
                shadowColor: '#000000',
                shadowOffset: { width: 0, height: 4 },
                shadowOpacity: 0.15,
                shadowRadius: 6,
                elevation: 4,
                transform: [{ scale: scaleValue }],
              },
            ]}
          >
            {/* Record Icon (Red circle/square) */}
            <View
              style={[
                styles.icon,
                {
                  width: recordIconSize,
                  height: recordIconSize,
                  borderRadius: isRecording ? 4 : recordIconSize / 2,
                  backgroundColor: theme.colors.error,
                },
              ]}
            />
          </Animated.View>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  pulseRing: {
    position: 'absolute',
  },
  borderRing: {
    borderWidth: 3,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 3,
  },
  touchArea: {
    width: '100%',
    height: '100%',
    justifyContent: 'center',
    alignItems: 'center',
  },
  buttonCircle: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  icon: {},
});
