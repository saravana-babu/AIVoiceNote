import React, { useState } from 'react';
import { StyleSheet, View, useWindowDimensions, ScrollView } from 'react-native';
import { Text, useTheme } from 'react-native-paper';
import { Button, Input, Card } from '@voicemind/ui';
import {
  useResetPasswordRequestMutation,
  useResetPasswordConfirmMutation,
} from '../hooks/useAuth.js';

interface ResetPasswordScreenProps {
  onNavigateToLogin: () => void;
}

export const ResetPasswordScreen: React.FC<ResetPasswordScreenProps> = ({ onNavigateToLogin }) => {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;

  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const requestMutation = useResetPasswordRequestMutation();
  const confirmMutation = useResetPasswordConfirmMutation();

  const handleRequestReset = async () => {
    if (!email) {
      setErrorMsg('Please enter your email address');
      return;
    }
    setErrorMsg('');
    setSuccessMsg('');
    try {
      const res = await requestMutation.mutateAsync(email);
      // In development, the API returns the reset token for convenience
      if (res.reset_token) {
        setResetToken(res.reset_token);
        setStep(2);
        setSuccessMsg('Token retrieved! Please type your new password.');
      } else {
        setSuccessMsg('Reset instructions sent to your email.');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to request password reset';
      setErrorMsg(message);
    }
  };

  const handleConfirmReset = async () => {
    if (!newPassword || !confirmPassword) {
      setErrorMsg('Please enter new password');
      return;
    }
    if (newPassword.length < 6) {
      setErrorMsg('Password must be at least 6 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      setErrorMsg('Passwords do not match');
      return;
    }
    setErrorMsg('');
    setSuccessMsg('');
    try {
      await confirmMutation.mutateAsync({
        token: resetToken,
        newPassword,
      });
      setSuccessMsg('Password reset successfully! Redirecting...');
      setTimeout(() => {
        onNavigateToLogin();
      }, 2000);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to confirm password reset';
      setErrorMsg(message);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
      <Card style={[styles.card, isDesktop && styles.desktopCard]}>
        <View style={styles.header}>
          <Text variant="headlineLarge" style={styles.title}>
            Reset Password
          </Text>
          <Text variant="bodyMedium" style={{ color: theme.colors.secondary }}>
            {step === 1
              ? 'Enter your email to receive reset instructions.'
              : 'Enter your new password below.'}
          </Text>
        </View>

        {!!errorMsg && (
          <Text style={[styles.errorMsg, { color: theme.colors.error }]}>⚠️ {errorMsg}</Text>
        )}

        {!!successMsg && (
          <Text style={[styles.successMsg, { color: theme.colors.primary }]}>✅ {successMsg}</Text>
        )}

        {step === 1 ? (
          <>
            <Input
              label="Email Address"
              value={email}
              onChangeText={setEmail}
              placeholder="yourname@example.com"
              keyboardType="email-address"
              style={styles.field}
            />
            <Button
              title="Send Reset Code"
              onPress={handleRequestReset}
              loading={requestMutation.isPending}
              style={styles.actionBtn}
            />
          </>
        ) : (
          <>
            <Input
              label="Reset Token"
              value={resetToken}
              onChangeText={setResetToken}
              placeholder="reset-xxxx"
              style={styles.field}
            />
            <Input
              label="New Password"
              value={newPassword}
              onChangeText={setNewPassword}
              secureTextEntry
              placeholder="Choose new password (min 6 characters)"
              style={styles.field}
            />
            <Input
              label="Confirm New Password"
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              secureTextEntry
              placeholder="Re-enter new password"
              style={styles.field}
            />
            <Button
              title="Update Password"
              onPress={handleConfirmReset}
              loading={confirmMutation.isPending}
              style={styles.actionBtn}
            />
          </>
        )}

        <View style={styles.navRow}>
          <Text
            variant="bodyMedium"
            style={[styles.link, { color: theme.colors.primary }]}
            onPress={onNavigateToLogin}
          >
            Back to Sign In
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
  successMsg: {
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
