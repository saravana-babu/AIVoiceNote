import React, { useState } from 'react';
import { StyleSheet, View, useWindowDimensions, ScrollView } from 'react-native';
import { Text, useTheme } from 'react-native-paper';
import { Button, Input, Card } from '@voicemind/ui';
import { useRegisterMutation } from '../hooks/useAuth.js';

interface RegisterScreenProps {
  onNavigateToLogin: () => void;
}

export const RegisterScreen: React.FC<RegisterScreenProps> = ({ onNavigateToLogin }) => {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;

  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const registerMutation = useRegisterMutation();

  const handleRegister = async () => {
    if (!email || !password || !displayName) {
      setErrorMsg('Please fill in all fields');
      return;
    }
    if (password.length < 6) {
      setErrorMsg('Password must be at least 6 characters');
      return;
    }
    if (password !== confirmPassword) {
      setErrorMsg('Passwords do not match');
      return;
    }
    setErrorMsg('');
    try {
      await registerMutation.mutateAsync({ email, password, displayName });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed';
      setErrorMsg(message);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
      <Card style={StyleSheet.flatten([styles.card, isDesktop && styles.desktopCard])}>
        <View style={styles.header}>
          <Text variant="headlineLarge" style={styles.title}>
            Create Account
          </Text>
          <Text variant="bodyMedium" style={{ color: theme.colors.secondary }}>
            Join VoiceMind AI notes app today.
          </Text>
        </View>

        {!!errorMsg && (
          <Text style={[styles.errorMsg, { color: theme.colors.error }]}>⚠️ {errorMsg}</Text>
        )}

        <Input
          label="Display Name"
          value={displayName}
          onChangeText={setDisplayName}
          placeholder="John Doe"
          style={styles.field}
        />

        <Input
          label="Email Address"
          value={email}
          onChangeText={setEmail}
          placeholder="yourname@example.com"
          keyboardType="email-address"
          style={styles.field}
        />

        <Input
          label="Password"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          placeholder="Choose password (min 6 characters)"
          style={styles.field}
        />

        <Input
          label="Confirm Password"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          secureTextEntry
          placeholder="Re-enter password"
          style={styles.field}
        />

        <Button
          title="Create Account"
          onPress={handleRegister}
          loading={registerMutation.isPending}
          style={styles.actionBtn}
        />

        <View style={styles.navRow}>
          <Text variant="bodyMedium">Already have an account? </Text>
          <Text
            variant="bodyMedium"
            style={[styles.link, { color: theme.colors.primary }]}
            onPress={onNavigateToLogin}
          >
            Sign In
          </Text>
        </View>
      </Card>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  card: {
    width: '100%',
    padding: 24,
    borderRadius: 24,
  },
  desktopCard: {
    maxWidth: 450,
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontWeight: '800',
    marginBottom: 6,
  },
  errorMsg: {
    marginBottom: 16,
    textAlign: 'center',
    fontWeight: '600',
  },
  field: {
    marginBottom: 16,
  },
  actionBtn: {
    marginTop: 8,
    width: '100%',
  },
  navRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 20,
  },
  link: {
    fontWeight: '700',
  },
});
