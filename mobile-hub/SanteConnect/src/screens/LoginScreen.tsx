import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { authService } from '../services/auth';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LoginScreenProps {
  onLoginSuccess: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const LoginScreen: React.FC<LoginScreenProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    const trimmedEmail = email.trim();

    if (!trimmedEmail || !password) {
      setError('Veuillez remplir tous les champs.');
      return;
    }

    setError(null);
    setLoading(true);

    try {
      await authService.login(trimmedEmail, password);
      onLoginSuccess();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Une erreur est survenue.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {/* Branding */}
          <View style={styles.brandContainer}>
            <View style={styles.logoCircle}>
              <Text style={styles.logoIcon}>+</Text>
            </View>
            <Text style={styles.appName}>SanteConnect</Text>
            <Text style={styles.tagline}>Mood-IoT | Suivi intelligent</Text>
          </View>

          {/* Login form */}
          <View style={styles.formCard}>
            <Text style={styles.formTitle}>Connexion</Text>

            <View style={styles.inputWrapper}>
              <Text style={styles.inputLabel}>Adresse e-mail</Text>
              <TextInput
                style={styles.input}
                placeholder="exemple@email.com"
                placeholderTextColor="#a0aec0"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                autoCorrect={false}
                editable={!loading}
              />
            </View>

            <View style={styles.inputWrapper}>
              <Text style={styles.inputLabel}>Mot de passe</Text>
              <TextInput
                style={styles.input}
                placeholder="Votre mot de passe"
                placeholderTextColor="#a0aec0"
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                editable={!loading}
                onSubmitEditing={handleLogin}
              />
            </View>

            {error && (
              <View style={styles.errorBanner}>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            )}

            <TouchableOpacity
              style={[styles.loginButton, loading && styles.loginButtonDisabled]}
              onPress={handleLogin}
              disabled={loading}
              activeOpacity={0.8}
            >
              {loading ? (
                <ActivityIndicator color="#ffffff" />
              ) : (
                <Text style={styles.loginButtonText}>Se connecter</Text>
              )}
            </TouchableOpacity>
          </View>

          <Text style={styles.footer}>
            Plateforme de suivi psychiatrique IoT
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const BLUE_PRIMARY = '#0066CC';
const BLUE_DARK = '#004C99';
const BLUE_LIGHT = '#E8F4FD';
const WHITE = '#FFFFFF';
const GRAY_50 = '#F7FAFC';
const GRAY_100 = '#EDF2F7';
const GRAY_500 = '#718096';
const RED_50 = '#FFF5F5';
const RED_500 = '#E53E3E';
const RED_700 = '#C53030';

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: GRAY_50,
  },
  flex: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: 24,
    paddingVertical: 40,
  },

  // Branding
  brandContainer: {
    alignItems: 'center',
    marginBottom: 36,
  },
  logoCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: BLUE_PRIMARY,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
    shadowColor: BLUE_PRIMARY,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
  logoIcon: {
    fontSize: 36,
    fontWeight: '700',
    color: WHITE,
  },
  appName: {
    fontSize: 28,
    fontWeight: '800',
    color: BLUE_DARK,
    letterSpacing: 0.5,
  },
  tagline: {
    fontSize: 14,
    color: GRAY_500,
    marginTop: 4,
  },

  // Form card
  formCard: {
    backgroundColor: WHITE,
    borderRadius: 20,
    padding: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 4,
  },
  formTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#1A202C',
    marginBottom: 20,
  },

  // Inputs
  inputWrapper: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: GRAY_500,
    marginBottom: 6,
  },
  input: {
    backgroundColor: GRAY_100,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    color: '#1A202C',
    borderWidth: 1,
    borderColor: 'transparent',
  },

  // Error
  errorBanner: {
    backgroundColor: RED_50,
    borderRadius: 10,
    padding: 12,
    marginBottom: 16,
    borderLeftWidth: 4,
    borderLeftColor: RED_500,
  },
  errorText: {
    color: RED_700,
    fontSize: 13,
    fontWeight: '500',
  },

  // Button
  loginButton: {
    backgroundColor: BLUE_PRIMARY,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 4,
    shadowColor: BLUE_PRIMARY,
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 3,
  },
  loginButtonDisabled: {
    opacity: 0.7,
  },
  loginButtonText: {
    color: WHITE,
    fontSize: 16,
    fontWeight: '700',
  },

  // Footer
  footer: {
    textAlign: 'center',
    color: GRAY_500,
    fontSize: 12,
    marginTop: 32,
  },
});

export default LoginScreen;
