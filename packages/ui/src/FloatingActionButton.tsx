import React from 'react';
import { FAB as PaperFAB } from 'react-native-paper';
import { StyleSheet, ViewStyle } from 'react-native';

export interface FloatingActionButtonProps {
  icon: string;
  onPress: () => void;
  label?: string;
  style?: ViewStyle;
  accessibilityLabel?: string;
}

export const FloatingActionButton: React.FC<FloatingActionButtonProps> = ({
  icon,
  onPress,
  label,
  style,
  accessibilityLabel,
}) => {
  return (
    <PaperFAB
      icon={icon}
      label={label}
      onPress={onPress}
      style={[styles.fab, style]}
      accessibilityLabel={accessibilityLabel || label || 'Floating action button'}
      accessibilityRole="button"
    />
  );
};

const styles = StyleSheet.create({
  fab: {
    position: 'absolute',
    margin: 16,
    right: 0,
    bottom: 0,
    borderRadius: 16,
  },
});
