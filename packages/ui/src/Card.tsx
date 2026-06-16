import React from 'react';
import { Card as PaperCard, useTheme } from 'react-native-paper';
import { StyleSheet, ViewStyle } from 'react-native';

export interface CardProps {
  children: React.ReactNode;
  mode?: 'elevated' | 'outlined' | 'contained';
  style?: ViewStyle;
  onPress?: () => void;
  accessibilityLabel?: string;
}

export const Card: React.FC<CardProps> = ({
  children,
  mode = 'contained',
  style,
  onPress,
  accessibilityLabel,
}) => {
  const theme = useTheme();

  return (
    <PaperCard
      mode={mode}
      style={[
        styles.card,
        mode === 'contained' && { backgroundColor: theme.colors.surfaceVariant },
        style,
      ]}
      onPress={onPress}
      accessibilityLabel={accessibilityLabel}
      accessibilityRole={onPress ? 'button' : 'none'}
    >
      <PaperCard.Content style={styles.content}>{children}</PaperCard.Content>
    </PaperCard>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    overflow: 'hidden',
  },
  content: {
    padding: 16,
  },
});
