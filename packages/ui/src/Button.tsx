import React from 'react';
import { Button as PaperButton, useTheme } from 'react-native-paper';
import { StyleSheet, ViewStyle, TextStyle } from 'react-native';

export interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  disabled?: boolean;
  loading?: boolean;
  style?: ViewStyle;
  labelStyle?: TextStyle;
  accessibilityLabel?: string;
}

export const Button: React.FC<ButtonProps> = ({
  title,
  onPress,
  variant = 'primary',
  disabled = false,
  loading = false,
  style,
  labelStyle,
  accessibilityLabel,
}) => {
  const theme = useTheme();

  let mode: 'contained' | 'outlined' | 'text' = 'contained';
  let buttonColor: string | undefined = undefined;
  let textColor: string | undefined = undefined;

  if (variant === 'primary') {
    mode = 'contained';
    buttonColor = theme.colors.primary;
    textColor = theme.colors.onPrimary;
  } else if (variant === 'secondary') {
    mode = 'outlined';
    textColor = theme.colors.primary;
  } else if (variant === 'danger') {
    mode = 'contained';
    buttonColor = theme.colors.error;
    textColor = theme.colors.onError || '#FFFFFF';
  }

  return (
    <PaperButton
      mode={mode}
      onPress={onPress}
      disabled={disabled || loading}
      loading={loading}
      buttonColor={buttonColor}
      textColor={textColor}
      style={[styles.button, style]}
      labelStyle={[styles.label, labelStyle]}
      accessibilityLabel={accessibilityLabel || title}
      accessibilityRole="button"
      accessibilityState={{ disabled: disabled || loading }}
    >
      {title}
    </PaperButton>
  );
};

const styles = StyleSheet.create({
  button: {
    borderRadius: 12,
    paddingVertical: 4,
    minHeight: 48,
    justifyContent: 'center',
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
  },
});
