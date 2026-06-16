import React, { useEffect, useRef } from 'react';
import {
  StyleSheet,
  View,
  Animated,
  TouchableWithoutFeedback,
  useWindowDimensions,
  ViewStyle,
} from 'react-native';
import { Portal, useTheme, IconButton } from 'react-native-paper';

export interface BottomSheetProps {
  visible: boolean;
  onDismiss: () => void;
  children: React.ReactNode;
  containerStyle?: ViewStyle;
}

export const BottomSheet: React.FC<BottomSheetProps> = ({
  visible,
  onDismiss,
  children,
  containerStyle,
}) => {
  const theme = useTheme();
  const { width, height } = useWindowDimensions();
  const isDesktop = width > 768;

  // Animation values
  const animatedValue = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      // Slide up / in
      Animated.timing(animatedValue, {
        toValue: 1,
        duration: 250,
        useNativeDriver: true,
      }).start();
    } else {
      // Slide down / out
      Animated.timing(animatedValue, {
        toValue: 0,
        duration: 200,
        useNativeDriver: true,
      }).start();
    }
  }, [visible, animatedValue]);

  if (!visible) return null;

  // Define translation directions:
  // Mobile: Slide up from bottom (translate Y)
  // Desktop: Slide in from right (translate X)
  const translateStyle = isDesktop
    ? {
        transform: [
          {
            translateX: animatedValue.interpolate({
              inputRange: [0, 1],
              outputRange: [400, 0],
            }),
          },
        ],
      }
    : {
        transform: [
          {
            translateY: animatedValue.interpolate({
              inputRange: [0, 1],
              outputRange: [height, 0],
            }),
          },
        ],
      };

  const backdropOpacity = animatedValue.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 0.5],
  });

  return (
    <Portal>
      <View style={StyleSheet.absoluteFillObject}>
        {/* Backdrop overlay */}
        <TouchableWithoutFeedback onPress={onDismiss} accessibilityLabel="Close sheet">
          <Animated.View
            style={[
              styles.backdrop,
              {
                opacity: backdropOpacity,
                backgroundColor: '#000000',
              },
            ]}
          />
        </TouchableWithoutFeedback>

        {/* Sheet container */}
        <Animated.View
          style={[
            styles.sheet,
            { backgroundColor: theme.colors.elevation.level2 },
            isDesktop ? styles.desktopSheet : styles.mobileSheet,
            translateStyle,
            containerStyle,
          ]}
          accessibilityRole="none"
        >
          {/* Top handle bar / close button */}
          <View style={styles.header}>
            {!isDesktop && (
              <View style={[styles.handle, { backgroundColor: theme.colors.outline }]} />
            )}
            {isDesktop && (
              <IconButton
                icon="close"
                size={20}
                onPress={onDismiss}
                style={styles.closeBtn}
                accessibilityLabel="Close"
              />
            )}
          </View>

          {/* Sheet Body Content */}
          <View style={styles.body}>{children}</View>
        </Animated.View>
      </View>
    </Portal>
  );
};

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
  },
  sheet: {
    position: 'absolute',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
    elevation: 10,
  },
  mobileSheet: {
    bottom: 0,
    left: 0,
    right: 0,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: '80%',
    paddingBottom: 24,
  },
  desktopSheet: {
    top: 0,
    right: 0,
    bottom: 0,
    width: 400,
    borderTopLeftRadius: 20,
    borderBottomLeftRadius: 20,
    paddingTop: 16,
  },
  header: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 8,
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    marginBottom: 8,
  },
  closeBtn: {
    alignSelf: 'flex-start',
    marginLeft: 12,
  },
  body: {
    flex: 1,
    paddingHorizontal: 20,
  },
});
