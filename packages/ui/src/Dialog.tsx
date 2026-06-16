import React from 'react';
import { Dialog as PaperDialog, Portal, Paragraph, Button } from 'react-native-paper';
import { StyleSheet, useWindowDimensions } from 'react-native';

export interface DialogProps {
  visible: boolean;
  onDismiss: () => void;
  title: string;
  content: string | React.ReactNode;
  confirmLabel?: string;
  onConfirm?: () => void;
  cancelLabel?: string;
  onCancel?: () => void;
  loadingConfirm?: boolean;
}

export const Dialog: React.FC<DialogProps> = ({
  visible,
  onDismiss,
  title,
  content,
  confirmLabel = 'OK',
  onConfirm,
  cancelLabel,
  onCancel,
  loadingConfirm = false,
}) => {
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;

  return (
    <Portal>
      <PaperDialog
        visible={visible}
        onDismiss={onDismiss}
        style={[styles.dialog, isDesktop && styles.desktopDialog]}
      >
        <PaperDialog.Title style={styles.title}>{title}</PaperDialog.Title>
        <PaperDialog.Content>
          {typeof content === 'string' ? (
            <Paragraph style={styles.text}>{content}</Paragraph>
          ) : (
            content
          )}
        </PaperDialog.Content>
        <PaperDialog.Actions style={styles.actions}>
          {cancelLabel && onCancel && (
            <Button onPress={onCancel} disabled={loadingConfirm} labelStyle={styles.actionLabel}>
              {cancelLabel}
            </Button>
          )}
          {onConfirm && (
            <Button
              onPress={onConfirm}
              loading={loadingConfirm}
              disabled={loadingConfirm}
              labelStyle={styles.confirmActionLabel}
            >
              {confirmLabel}
            </Button>
          )}
        </PaperDialog.Actions>
      </PaperDialog>
    </Portal>
  );
};

const styles = StyleSheet.create({
  dialog: {
    borderRadius: 20,
    alignSelf: 'center',
    width: '90%',
    maxWidth: 400,
  },
  desktopDialog: {
    maxWidth: 450,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
  },
  text: {
    fontSize: 15,
  },
  actions: {
    paddingRight: 16,
    paddingBottom: 8,
  },
  actionLabel: {
    fontWeight: '600',
  },
  confirmActionLabel: {
    fontWeight: '700',
  },
});
