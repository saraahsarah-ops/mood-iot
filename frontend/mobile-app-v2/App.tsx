import React, { useEffect, useRef } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import {
  Text, View, StyleSheet, TextInput,
  TouchableOpacity, KeyboardAvoidingView, Platform,
  ActivityIndicator, Animated, Easing, Modal, Pressable,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

import { useAuthStore } from './src/store/authStore';
import Recommandations from './src/screens/Recommandations';
import Mesures from './src/screens/Mesures';
import Tchat from './src/screens/Tchat';
import Profil from './src/screens/Profil';

const Tab = createBottomTabNavigator();

// ────────────────────────────────────────────────────────────────────────────
// Toast
// ────────────────────────────────────────────────────────────────────────────

interface ToastProps {
  message: string;
  kind: 'success' | 'error';
  visible: boolean;
}

function Toast({ message, kind, visible }: ToastProps) {
  const opacity = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(-12)).current;

  useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.timing(opacity, {
          toValue: 1, duration: 220,
          easing: Easing.out(Easing.ease), useNativeDriver: true,
        }),
        Animated.timing(translateY, {
          toValue: 0, duration: 220,
          easing: Easing.out(Easing.ease), useNativeDriver: true,
        }),
      ]).start();
    } else {
      Animated.parallel([
        Animated.timing(opacity,    { toValue: 0, duration: 180, useNativeDriver: true }),
        Animated.timing(translateY, { toValue: -12, duration: 180, useNativeDriver: true }),
      ]).start();
    }
  }, [visible]);

  const isSuccess = kind === 'success';
  return (
    <Animated.View
      style={[
        toastStyles.container,
        isSuccess ? toastStyles.success : toastStyles.error,
        { opacity, transform: [{ translateY }] },
      ]}
      pointerEvents="none"
    >
      <Text style={toastStyles.icon}>{isSuccess ? '✅' : '❌'}</Text>
      <Text style={[toastStyles.text, isSuccess ? toastStyles.textSuccess : toastStyles.textError]}>
        {message}
      </Text>
    </Animated.View>
  );
}

const toastStyles = StyleSheet.create({
  container: {
    position: 'absolute', top: 56, left: 20, right: 20,
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 13, paddingHorizontal: 16,
    borderRadius: 14, zIndex: 999, borderWidth: 1,
  },
  success:     { backgroundColor: '#EBF8F4', borderColor: '#A3D9C9' },
  error:       { backgroundColor: '#FBEAE8', borderColor: '#F4B8B0' },
  icon:        { fontSize: 16 },
  text:        { flex: 1, fontSize: 13, fontWeight: '600', lineHeight: 18 },
  textSuccess: { color: '#1B5E4A' },
  textError:   { color: '#B5362A' },
});

// ────────────────────────────────────────────────────────────────────────────
// Tab icon (tabs normaux)
// ────────────────────────────────────────────────────────────────────────────

const TabIcon = ({ emoji, label, focused }: { emoji: string; label: string; focused: boolean }) => (
  <View style={tabStyles.iconWrap}>
    <Text style={tabStyles.emoji}>{emoji}</Text>
    <Text style={[tabStyles.label, focused && tabStyles.labelActive]}>{label}</Text>
  </View>
);

// ────────────────────────────────────────────────────────────────────────────
// Profile menu (Modal)
// ────────────────────────────────────────────────────────────────────────────

function ProfileMenu({
  visible, onClose, onGoProfile, onSignOut,
}: {
  visible: boolean;
  onClose: () => void;
  onGoProfile: () => void;
  onSignOut: () => void;
}) {
  return (
    <Modal
      transparent
      visible={visible}
      animationType="fade"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <Pressable style={pmStyles.backdrop} onPress={onClose}>
        <View style={pmStyles.menu}>
          <TouchableOpacity style={pmStyles.item} onPress={onGoProfile} activeOpacity={0.7}>
            <Text style={pmStyles.itemIcon}>👤</Text>
            <Text style={pmStyles.itemText}>Mon profil</Text>
          </TouchableOpacity>
          <View style={pmStyles.separator} />
          <TouchableOpacity style={pmStyles.item} onPress={onSignOut} activeOpacity={0.7}>
            <Text style={pmStyles.itemIcon}>🚪</Text>
            <Text style={[pmStyles.itemText, pmStyles.danger]}>Se déconnecter</Text>
          </TouchableOpacity>
        </View>
      </Pressable>
    </Modal>
  );
}

const pmStyles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.18)', justifyContent: 'flex-end' },
  menu: {
    backgroundColor: '#fff', borderRadius: 20,
    marginHorizontal: 16, marginBottom: 88,
    overflow: 'hidden', borderWidth: 1, borderColor: '#DCEAE5',
  },
  item:      { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 16, paddingHorizontal: 20 },
  itemIcon:  { fontSize: 18 },
  itemText:  { fontSize: 15, fontWeight: '600', color: '#1B3A3A' },
  separator: { height: 1, backgroundColor: '#DCEAE5' },
  danger:    { color: '#C45850' },
});

// ────────────────────────────────────────────────────────────────────────────
// Error helpers
// ────────────────────────────────────────────────────────────────────────────

type ErrorKind = 'credentials' | 'network' | 'server' | 'validation' | null;

function categorizeError(msg: string): ErrorKind {
  if (!msg) return null;
  if (msg.includes('incorrect') || msg.includes('Invalid user')) return 'credentials';
  if (
    msg.includes('Network') || msg.includes('fetch') ||
    msg.includes('connexion impossible') || msg.includes('ECONNREFUSED') ||
    msg.includes('network') || msg.includes('réseau')
  ) return 'network';
  if (msg.includes('HTTP 5') || msg.includes('serveur')) return 'server';
  return 'credentials';
}

const ERROR_CONFIG: Record<NonNullable<ErrorKind>, { icon: string; title: string; color: string; bg: string }> = {
  credentials: { icon: '🔑', title: 'Identifiants incorrects', color: '#C45850', bg: '#FBEAE8' },
  network:     { icon: '📡', title: 'Serveur inaccessible',    color: '#C9852B', bg: '#FBF2E3' },
  server:      { icon: '⚠️', title: 'Erreur serveur',          color: '#C9852B', bg: '#FBF2E3' },
  validation:  { icon: '✏️', title: 'Champs invalides',        color: '#C45850', bg: '#FBEAE8' },
};

// ────────────────────────────────────────────────────────────────────────────
// Login screen
// ────────────────────────────────────────────────────────────────────────────

function LoginScreen() {
  const { signInWithEmailPassword, signingIn, error } = useAuthStore();

  const [email, setEmail]               = React.useState('marie.dupont@example.test');
  const [password, setPassword]         = React.useState('Marie2026!');
  const [showPassword, setShowPassword] = React.useState(false);
  const [emailTouched, setEmailTouched] = React.useState(false);
  const [passwordTouched, setPasswordTouched] = React.useState(false);

  const [toast, setToast]           = React.useState<{ message: string; kind: 'success' | 'error' } | null>(null);
  const [toastVisible, setToastVisible] = React.useState(false);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (message: string, kind: 'success' | 'error') => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ message, kind });
    setToastVisible(true);
    toastTimerRef.current = setTimeout(() => setToastVisible(false), 3000);
  };

  const emailError    = emailTouched    && !email.includes('@') ? 'Adresse e-mail invalide' : null;
  const passwordError = passwordTouched && password.length < 4  ? 'Mot de passe trop court' : null;
  const errorKind     = categorizeError(error ?? '');
  const errorCfg      = errorKind ? ERROR_CONFIG[errorKind] : null;

  const handleEmailLogin = async () => {
    setEmailTouched(true);
    setPasswordTouched(true);
    if (emailError || passwordError || !email || !password) return;
    try {
      await signInWithEmailPassword(email, password);
      showToast('Connexion réussie !', 'success');
    } catch {
      showToast(error ?? 'Connexion échouée. Vérifiez vos identifiants.', 'error');
    }
  };

  return (
    <SafeAreaView style={ls.root} edges={['top', 'bottom']}>
      {toast && <Toast message={toast.message} kind={toast.kind} visible={toastVisible} />}

      <KeyboardAvoidingView style={ls.kav} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <View style={ls.inner}>
          {signingIn && (
            <View style={ls.loaderOverlay}>
              <View style={ls.loaderCard}>
                <ActivityIndicator color="#2D7D6E" size="large" />
                <Text style={ls.loaderText}>Connexion en cours…</Text>
              </View>
            </View>
          )}

          <Text style={ls.logo}>🌿</Text>
          <Text style={ls.appName}>Mood-IoT</Text>
          <Text style={ls.subtitle}>Suivi santé sécurisé</Text>

          <View style={ls.form}>
            {errorCfg && error && !signingIn && (
              <View style={[ls.errorBox, { backgroundColor: errorCfg.bg, borderLeftColor: errorCfg.color }]}>
                <Text style={ls.errorIcon}>{errorCfg.icon}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={[ls.errorTitle, { color: errorCfg.color }]}>{errorCfg.title}</Text>
                  <Text style={[ls.errorMsg,   { color: errorCfg.color }]}>{error}</Text>
                  {errorKind === 'network' && (
                    <Text style={ls.errorHint}>Vérifiez votre connexion internet ou réessayez dans quelques instants.</Text>
                  )}
                </View>
              </View>
            )}

            <Text style={ls.fieldLabel}>Adresse e-mail</Text>
            <TextInput
              style={[ls.input, emailError ? ls.inputError : null]}
              placeholder="sophie@exemple.fr"
              placeholderTextColor="#5B7672"
              value={email}
              onChangeText={(v) => { setEmail(v); setEmailTouched(true); }}
              onBlur={() => setEmailTouched(true)}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              editable={!signingIn}
            />
            {emailError && <Text style={ls.fieldError}>{emailError}</Text>}

            <Text style={ls.fieldLabel}>Mot de passe</Text>
            <View style={ls.passwordWrap}>
              <TextInput
                style={[ls.inputPassword, passwordError ? ls.inputError : null]}
                placeholder="••••••••"
                placeholderTextColor="#5B7672"
                value={password}
                onChangeText={(v) => { setPassword(v); setPasswordTouched(true); }}
                onBlur={() => setPasswordTouched(true)}
                secureTextEntry={!showPassword}
                editable={!signingIn}
              />
              <TouchableOpacity style={ls.eyeBtn} onPress={() => setShowPassword(v => !v)}>
                <Text style={ls.eyeIcon}>{showPassword ? '🙈' : '👁️'}</Text>
              </TouchableOpacity>
            </View>
            {passwordError && <Text style={ls.fieldError}>{passwordError}</Text>}

            <TouchableOpacity style={ls.forgotWrap}>
              <Text style={ls.forgot}>Mot de passe oublié ?</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[ls.btn, signingIn && ls.btnDisabled]}
              onPress={handleEmailLogin}
              disabled={signingIn}
            >
              <Text style={ls.btnText}>Se connecter</Text>
            </TouchableOpacity>

            {errorKind === 'network' && !signingIn && (
              <TouchableOpacity style={ls.retryBtn} onPress={handleEmailLogin}>
                <Text style={ls.retryText}>🔄 Réessayer</Text>
              </TouchableOpacity>
            )}

            <View style={ls.dividerRow}>
              <View style={ls.dividerLine} />
              <Text style={ls.dividerText}>ou</Text>
              <View style={ls.dividerLine} />
            </View>

            <TouchableOpacity
              style={[ls.btnOutline, signingIn && ls.btnDisabled]}
              onPress={() => {/* navigation vers écran inscription */}}
              disabled={signingIn}
            >
              <Text style={ls.btnOutlineText}>Créer un compte</Text>
            </TouchableOpacity>
          </View>

          <Text style={ls.legal}>
            Vos données sont chiffrées et confidentielles.{'\n'}
            Seul votre médecin y a accès.
          </Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Splash
// ────────────────────────────────────────────────────────────────────────────

function SplashScreen() {
  return (
    <View style={splash.root}>
      <Text style={splash.logo}>🌿</Text>
      <ActivityIndicator color="#2D7D6E" style={{ marginTop: 24 }} />
    </View>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// App
// ────────────────────────────────────────────────────────────────────────────

export default function App() {
  const { tokens, loading, restore, signOut, user } = useAuthStore();
  const [menuVisible, setMenuVisible] = React.useState(false);
  const navigationRef = React.useRef<any>(null);

  useEffect(() => { restore(); }, []);

  const initials = React.useMemo(() => {
    if (!user) return '??';
    const first = user.first_name?.[0] ?? '';
    const last  = user.last_name?.[0]  ?? '';
    return (first + last).toUpperCase() || '??';
  }, [user]);

  if (loading) return <SafeAreaProvider><SplashScreen /></SafeAreaProvider>;
  if (!tokens) return <SafeAreaProvider><LoginScreen /></SafeAreaProvider>;

  return (
    <SafeAreaProvider>
      <NavigationContainer ref={navigationRef}>

        {/* Menu profil global — rendu en dehors du Navigator pour le Modal */}
        <ProfileMenu
          visible={menuVisible}
          onClose={() => setMenuVisible(false)}
          onGoProfile={() => {
            setMenuVisible(false);
            navigationRef.current?.navigate('Profil');
          }}
          onSignOut={() => {
            setMenuVisible(false);
            signOut();
          }}
        />

        <Tab.Navigator
          screenOptions={{
            headerShown: false,
            tabBarStyle: tabStyles.bar,
            tabBarShowLabel: false,
          }}
        >
          <Tab.Screen
            name="Recommandations"
            component={Recommandations}
            options={{
              tabBarIcon: ({ focused }) => <TabIcon emoji="💬" label="Recommandations" focused={focused} />,
            }}
          />
          <Tab.Screen
            name="Mesures"
            component={Mesures}
            options={{
              tabBarIcon: ({ focused }) => <TabIcon emoji="📊" label="Mes mesures" focused={focused} />,
            }}
          />
          <Tab.Screen
            name="Tchat"
            component={Tchat}
            options={{
              tabBarIcon: ({ focused }) => <TabIcon emoji="🩺" label="Médecin" focused={focused} />,
            }}
          />

          {/*
           * Onglet Profil : on remplace ENTIÈREMENT le bouton natif via tabBarButton
           * pour intercepter le tap et ouvrir le menu au lieu de naviguer.
           */}
          <Tab.Screen
            name="Profil"
            component={Profil}
            options={{
              tabBarButton: ({ accessibilityState }) => (
                <TouchableOpacity
                  style={tabStyles.profileBtn}
                  onPress={() => setMenuVisible(true)}
                  activeOpacity={0.7}
                >
                  <View style={[
                    profileTabStyles.avatar,
                    accessibilityState?.selected && profileTabStyles.avatarFocused,
                  ]}>
                    <Text style={profileTabStyles.initials}>{initials}</Text>
                  </View>
                  <Text style={[
                    tabStyles.label,
                    accessibilityState?.selected && tabStyles.labelActive,
                  ]}>
                    Profil
                  </Text>
                </TouchableOpacity>
              ),
            }}
          />
        </Tab.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Styles
// ────────────────────────────────────────────────────────────────────────────

const ls = StyleSheet.create({
  root:     { flex: 1, backgroundColor: '#F4FAF8' },
  kav:      { flex: 1 },
  inner:    { flex: 1, justifyContent: 'center', padding: 28 },
  logo:     { fontSize: 52, textAlign: 'center', marginBottom: 8 },
  appName:  { fontSize: 28, fontWeight: '700', color: '#1B3A3A', textAlign: 'center' },
  subtitle: { fontSize: 14, color: '#5B7672', textAlign: 'center', marginTop: 4, marginBottom: 36 },
  form:     { backgroundColor: '#fff', borderRadius: 24, padding: 24, borderWidth: 1, borderColor: '#DCEAE5' },

  loaderOverlay: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(244,250,248,0.85)', zIndex: 10,
    alignItems: 'center', justifyContent: 'center',
  },
  loaderCard: {
    backgroundColor: '#fff', borderRadius: 20, padding: 28,
    alignItems: 'center', gap: 14, borderWidth: 1, borderColor: '#DCEAE5', minWidth: 180,
  },
  loaderText: { fontSize: 14, color: '#2D7D6E', fontWeight: '600' },

  errorBox: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    borderRadius: 12, padding: 12, marginBottom: 16, borderLeftWidth: 3,
  },
  errorIcon:  { fontSize: 18, marginTop: 1 },
  errorTitle: { fontSize: 13, fontWeight: '700', marginBottom: 2 },
  errorMsg:   { fontSize: 12, lineHeight: 17 },
  errorHint:  { fontSize: 11, color: '#5B7672', marginTop: 4, fontStyle: 'italic' },

  fieldError: { fontSize: 11, color: '#C45850', fontWeight: '600', marginTop: -8, marginBottom: 8, marginLeft: 4 },
  inputError: { borderColor: '#C45850', borderWidth: 1.5 },
  fieldLabel: { fontSize: 12, fontWeight: '700', color: '#5B7672', marginBottom: 6, marginTop: 4 },

  input: {
    backgroundColor: '#F4FAF8', borderRadius: 12,
    paddingHorizontal: 14, paddingVertical: 12,
    fontSize: 14, color: '#1B3A3A',
    borderWidth: 1, borderColor: '#DCEAE5', marginBottom: 4,
  },
  passwordWrap: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#F4FAF8', borderRadius: 12,
    borderWidth: 1, borderColor: '#DCEAE5', marginBottom: 4,
  },
  inputPassword: {
    flex: 1, paddingHorizontal: 14, paddingVertical: 12,
    fontSize: 14, color: '#1B3A3A',
  },
  eyeBtn:     { paddingHorizontal: 12, paddingVertical: 10 },
  eyeIcon:    { fontSize: 18 },
  forgot:     { fontSize: 12, color: '#2D7D6E', fontWeight: '600' },
  forgotWrap: { alignSelf: 'flex-end', marginBottom: 14, marginTop: 2 },

  btn:         { backgroundColor: '#2D7D6E', borderRadius: 14, paddingVertical: 15, alignItems: 'center' },
  btnDisabled: { opacity: 0.6 },
  btnText:     { color: '#fff', fontSize: 15, fontWeight: '700' },

  retryBtn:  { marginTop: 10, alignItems: 'center', paddingVertical: 8 },
  retryText: { fontSize: 13, color: '#C9852B', fontWeight: '700' },

  dividerRow:  { flexDirection: 'row', alignItems: 'center', marginVertical: 16, gap: 8 },
  dividerLine: { flex: 1, height: 1, backgroundColor: '#DCEAE5' },
  dividerText: { fontSize: 12, color: '#5B7672' },

  btnOutline:     { borderWidth: 1.5, borderColor: '#2D7D6E', borderRadius: 14, paddingVertical: 14, alignItems: 'center' },
  btnOutlineText: { color: '#2D7D6E', fontSize: 13, fontWeight: '700' },

  legal: { marginTop: 24, textAlign: 'center', fontSize: 11, color: '#5B7672', lineHeight: 17 },
});

const tabStyles = StyleSheet.create({
  bar: {
    backgroundColor: '#FFFFFF', borderTopColor: '#DCEAE5',
    borderTopWidth: 1, height: 68, paddingBottom: 8, paddingTop: 6,
  },
  iconWrap:   { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 4 },
  // Le bouton profil occupe le même espace flex qu'un onglet normal
  profileBtn: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 4 },
  emoji:      { fontSize: 20 },
  label:      { fontSize: 10, fontWeight: '600', color: '#5B7672', marginTop: 2 },
  labelActive:{ color: '#2D7D6E' },
});

const profileTabStyles = StyleSheet.create({
  avatar: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: '#E1F5EE',
    borderWidth: 1.5, borderColor: '#A3C9C0',
    alignItems: 'center', justifyContent: 'center',
  },
  avatarFocused: { borderColor: '#2D7D6E', backgroundColor: '#C5EDE0' },
  initials: { fontSize: 10, fontWeight: '700', color: '#2D7D6E' },
});

const splash = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F4FAF8', alignItems: 'center', justifyContent: 'center' },
  logo: { fontSize: 64 },
});