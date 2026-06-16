import React from 'react';
import { Portal, Modal as PaperModal, useTheme } from 'react-native-paper';
import { StyleSheet, View, useWindowDimensions, ViewStyle, ScrollView } from 'react-native';

export interface ModalProps {
  visible: boolean;
  onDismiss: () => void;
  children: React.ReactNode;
  contentContainerStyle?: ViewStyle;
}

export const Modal: React.FC<ModalProps> = ({
  visible,
  onDismiss,
  children,
  contentContainerStyle,
}) => {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;

  // Max width of 550px for desktop to make it look clean
  const containerStyle = [
    styles.container,
    { backgroundColor: theme.colors.elevation.level3 },
    isDesktop && styles.desktopContainer,
    contentContainerStyle,
  ];

  return (
    <Portal>
      <PaperModal
        visible={visible}
        onDismiss={onDismiss}
        contentContainerStyle={containerStyle}
        style={styles.modalOverlay}
      >
        <ScrollView contentContainerStyle={styles.scrollContent} bounces={false}>
          <View accessibilityViewIsModal={true} accessibilityRole="none">
            {children}
          </View>
        </ScrollView>
      </PaperModal>
    </Portal>
  );
};

const styles = StyleSheet.create({
  modalOverlay: {
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  container: {
    padding: 20,
    borderRadius: 20,
    width: '100%',
    maxHeight: '80%',
  },
  desktopContainer: {
    maxWidth: 550,
  },
  scrollContent: {
    flexGrow: 0,
  },
});
