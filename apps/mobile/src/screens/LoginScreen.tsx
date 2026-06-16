import React, { useState } from 'react';
import { StyleSheet, View, useWindowDimensions, ScrollView } from 'react-native';
import { Text, useTheme } from 'react-native-paper';
import { Button, Input, Card } from '@voicemind/ui';
import {
  useLoginMutation,
  useGoogleLoginMutation,
  useAppleLoginMutation,
} from '../hooks/useAuth.js';

interface LoginScreenProps {
  onNavigateToRegister: () => void;
  onNavigateToReset: () => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({
  onNavigateToRegister,
  onNavigateToReset,
}) => {
  const theme = useTheme();
  const { width } = useWindowDimensions();
  const isDesktop = width > 768;

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const loginMutation = useLoginMutation();
  const googleMutation = useGoogleLoginMutation();
  const appleMutation = useAppleLoginMutation();

  const handleLogin = async () => {
    if (!email || !password) {
      setErrorMsg('Please fill in all fields');
      return;
    }
    setErrorMsg('');
    try {
      await loginMutation.mutateAsync({ email, password });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setErrorMsg(message);
    }
  };

  const handleOAuth = async (provider: 'google' | 'apple') => {
    if (!email) {
      setErrorMsg('Please enter your email first to simulate OAuth');
      return;
    }
    setErrorMsg('');
    try {
      if (provider === 'google') {
        await googleMutation.mutateAsync({ email });
      } else {
        await appleMutation.mutateAsync({ email });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : `${provider} authentication failed`;
      setErrorMsg(message);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
      <Card style={[styles.card, isDesktop && styles.desktopCard]}>
        <View style={styles.header}>
          <Text variant="headlineLarge" style={styles.title}>
            VoiceMind AI
          </Text>
          <Text variant="bodyMedium" style={{ color: theme.colors.secondary }}>
            Welcome back! Please sign in.
          </Text>
        </View>

        {!!errorMsg && (
          <Text style={[styles.errorMsg, { color: theme.colors.error }]}>⚠️ {errorMsg}</Text>
        )}

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
          placeholder="Enter password"
          style={styles.field}
        />

        <Button
          title="Sign In with Email"
          onPress={handleLogin}
          loading={loginMutation.isPending}
          style={styles.actionBtn}
        />

        <View style={styles.navRow}>
          <Text variant="bodyMedium">Don't have an account? </Text>
          <Text
            variant="bodyMedium"
            style={[styles.link, { color: theme.colors.primary }]}
            onPress={onNavigateToRegister}
          >
            Sign Up
          </Text>
        </View>

        <Text
          variant="bodyMedium"
          style={[styles.forgotLink, { color: theme.colors.outline }]}
          onPress={onNavigateToReset}
        >
          Forgot Password?
        </Text>

        <View style={styles.oauthDivider}>
          <View style={[styles.dividerLine, { backgroundColor: theme.colors.outline }]} />
          <Text style={[styles.dividerText, { color: theme.colors.outline }]}>
            or continue with
          </Text>
          <View style={[styles.dividerLine, { backgroundColor: theme.colors.outline }]} />
        </View>

        <View style={styles.oauthRow}>
          <Button
            title="Google"
            onPress={() => handleOAuth('google')}
            variant="secondary"
            loading={googleMutation.isPending}
            style={styles.oauthBtn}
          />
          <Button
            title="Apple"
            onPress={() => handleOAuth('apple')}
            variant="secondary"
            loading={appleMutation.isPending}
            style={styles.oauthBtn}
          />
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
  forgotLink: {
    textAlign: 'center',
    marginTop: 12,
    fontWeight: '600',
  },
  oauthDivider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 24,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    opacity: 0.2,
  },
  dividerText: {
    marginHorizontal: 12,
    fontSize: 13,
  },
  oauthRow: {
    flexDirection: 'row',
    gap: 12,
  },
  oauthBtn: {
    flex: 1,
  },
});
