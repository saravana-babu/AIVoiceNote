import React, { useState } from 'react';
import { TextInput as PaperTextInput, HelperText } from 'react-native-paper';
import { StyleSheet, View, ViewStyle, TextStyle } from 'react-native';

export interface InputProps {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  error?: string;
  secureTextEntry?: boolean;
  style?: ViewStyle;
  inputStyle?: TextStyle;
  keyboardType?: 'default' | 'email-address' | 'numeric' | 'phone-pad';
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  rightIcon?: string;
  onRightIconPress?: () => void;
}

export const Input: React.FC<InputProps> = ({
  label,
  value,
  onChangeText,
  placeholder,
  error,
  secureTextEntry = false,
  style,
  inputStyle,
  keyboardType = 'default',
  autoCapitalize = 'none',
  rightIcon,
  onRightIconPress,
}) => {
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = secureTextEntry;

  const getRightIcon = () => {
    if (isPassword) {
      return (
        <PaperTextInput.Icon
          icon={showPassword ? 'eye-off' : 'eye'}
          onPress={() => setShowPassword(!showPassword)}
          accessibilityLabel={showPassword ? 'Hide password' : 'Show password'}
        />
      );
    }
    if (rightIcon) {
      return (
        <PaperTextInput.Icon
          icon={rightIcon}
          onPress={onRightIconPress}
          accessibilityLabel="Input action"
        />
      );
    }
    return null;
  };

  return (
    <View style={[styles.container, style]}>
      <PaperTextInput
        label={label}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        error={!!error}
        secureTextEntry={isPassword && !showPassword}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize}
        mode="outlined"
        outlineStyle={styles.outline}
        style={[styles.input, inputStyle]}
        right={getRightIcon()}
        accessibilityLabel={label}
        accessibilityRole="text"
      />
      {!!error && (
        <HelperText type="error" visible={true} style={styles.errorText}>
          {error}
        </HelperText>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginVertical: 6,
    width: '100%',
  },
  input: {
    backgroundColor: 'transparent',
  },
  outline: {
    borderRadius: 12,
  },
  errorText: {
    paddingLeft: 8,
  },
});
