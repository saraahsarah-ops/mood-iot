import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  Platform,
  Alert,
  ScrollView,
  PermissionsAndroid,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import Geolocation from 'react-native-geolocation-service';
import * as HealthConnect from 'react-native-health-connect';
import {
  login,
  logout,
  syncHealthData,
  isAuthenticated,
  getPatientId,
  setPatientId,
  type HealthDataPayload,
} from './src/services/api';

const App = () => {
  // --- Auth state ---
  const [loggedIn, setLoggedIn] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [userName, setUserName] = useState('');

  // --- Health data state ---
  const [steps, setSteps] = useState<number | string>('--');
  const [heartRate, setHeartRate] = useState<number | string>('--');
  const [sleepDisplay, setSleepDisplay] = useState('--');
  const [sleepMinutes, setSleepMinutes] = useState<number | null>(null);
  const [location, setLocation] = useState<{ latitude: number; longitude: number } | null>(null);

  // --- Sync state ---
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [lastSync, setLastSync] = useState<string | null>(null);

  const isAndroid = Platform.OS === 'android';

  // =====================================================================
  // AUTHENTIFICATION
  // =====================================================================

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('Erreur', 'Veuillez saisir email et mot de passe');
      return;
    }

    setAuthLoading(true);
    try {
      const data = await login(email, password);
      const user = data.user;
      setUserName(user?.first_name || user?.email || 'Patient');

      // Si le backend ne retourne pas le patient_id dans le user,
      // on peut le demander ou le configurer manuellement
      if (!getPatientId() && user?.id) {
        setPatientId(user.id);
      }

      setLoggedIn(true);
      setPassword(''); // Ne pas garder le mdp en memoire
    } catch (err: any) {
      Alert.alert('Connexion echouee', err.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    setLoggedIn(false);
    setEmail('');
    setUserName('');
    setSyncStatus('idle');
    setLastSync(null);
    setSteps('--');
    setHeartRate('--');
    setSleepDisplay('--');
    setSleepMinutes(null);
    setLocation(null);
  };

  // =====================================================================
  // UTILITAIRES
  // =====================================================================

  const formatSleepDuration = (startTime: string, endTime: string) => {
    const durationMs = new Date(endTime).getTime() - new Date(startTime).getTime();
    const totalMinutes = Math.floor(durationMs / (1000 * 60));
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return { display: `${hours}h ${minutes}m`, totalMinutes };
  };

  const getTodayDate = () => {
    const d = new Date();
    return d.toISOString().split('T')[0]; // "2026-04-12"
  };

  // =====================================================================
  // 1. GPS
  // =====================================================================

  const fetchLocation = (): Promise<{ latitude: number; longitude: number } | null> => {
    return new Promise(async (resolve) => {
      if (Platform.OS === 'android') {
        const granted = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
        );
        if (granted !== PermissionsAndroid.RESULTS.GRANTED) {
          resolve(null);
          return;
        }
      }

      Geolocation.getCurrentPosition(
        (position) => {
          const loc = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          };
          setLocation(loc);
          resolve(loc);
        },
        (error) => {
          console.log('Erreur GPS:', error.message);
          resolve(null);
        },
        { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 },
      );
    });
  };

  // =====================================================================
  // 2. LECTURE HEALTH CONNECT + ENVOI AU BACKEND
  // =====================================================================

  const fetchAndSyncHealthData = async () => {
    if (!isAndroid) return;

    setSyncing(true);
    setSyncStatus('idle');

    try {
      // --- Initialisation et permissions Health Connect ---
      await HealthConnect.initialize();

      await HealthConnect.requestPermission([
        { accessType: 'read', recordType: 'Steps' },
        { accessType: 'read', recordType: 'HeartRate' },
        { accessType: 'read', recordType: 'SleepSession' },
      ]);

      const now = new Date();
      const startTimeToday = new Date();
      startTimeToday.setHours(0, 0, 0, 0);

      // --- RECUPERATION DES PAS ---
      let stepsValue: number | null = null;
      const stepAggregation = await HealthConnect.aggregateRecord({
        recordType: 'Steps',
        timeRangeFilter: {
          operator: 'between',
          startTime: startTimeToday.toISOString(),
          endTime: now.toISOString(),
        },
      });
      stepsValue = stepAggregation?.COUNT_TOTAL || 0;
      setSteps(stepsValue);

      // --- RECUPERATION DU COEUR ---
      let hrValue: number | null = null;
      const hrResult = await HealthConnect.readRecords('HeartRate', {
        timeRangeFilter: {
          operator: 'between',
          startTime: '2023-01-01T00:00:00Z',
          endTime: now.toISOString(),
        },
        ascendingOrder: false,
        pageSize: 1,
      });

      if (hrResult.records.length > 0) {
        const lastRecord = hrResult.records[0];
        const bpm =
          lastRecord.beatsPerMinute ||
          lastRecord.samples?.[lastRecord.samples.length - 1]?.beatsPerMinute;
        hrValue = Math.round(bpm) || null;
        setHeartRate(hrValue || '--');
      }

      // --- RECUPERATION DU SOMMEIL ---
      let sleepMin: number | null = null;
      const startOfSleepSearch = new Date();
      startOfSleepSearch.setDate(now.getDate() - 3);

      const sleepResult = await HealthConnect.readRecords('SleepSession', {
        timeRangeFilter: {
          operator: 'between',
          startTime: startOfSleepSearch.toISOString(),
          endTime: now.toISOString(),
        },
        ascendingOrder: false,
      });

      if (sleepResult.records.length > 0) {
        const lastNight = sleepResult.records[0];
        const { display, totalMinutes } = formatSleepDuration(
          lastNight.startTime,
          lastNight.endTime,
        );
        sleepMin = totalMinutes;
        setSleepDisplay(display);
        setSleepMinutes(totalMinutes);
      } else {
        setSleepDisplay('Zz..');
      }

      // --- GPS ---
      const loc = await fetchLocation();

      // =================================================================
      // ENVOI AU BACKEND (Patient Service)
      // =================================================================
      const patientId = getPatientId();
      if (!patientId) {
        Alert.alert(
          'Patient ID manquant',
          'Impossible d\'envoyer les donnees sans identifiant patient.',
        );
        setSyncing(false);
        return;
      }

      const payload: HealthDataPayload = {
        date: getTodayDate(),
        heart_rate_avg: hrValue,
        heart_rate_variability: null, // Health Connect ne fournit pas le HRV directement
        sleep_duration_min: sleepMin,
        sleep_quality_score: null,     // Pas disponible via Health Connect basique
        step_count: stepsValue,
        gps_radius_km: loc ? 0 : null, // Calcul du rayon a implementer cote backend
        gps_locations_count: loc ? 1 : null,
        screen_time_min: null,         // Necessite UsageStatsManager (Android)
        call_count: null,              // Necessite permissions supplementaires
        call_duration_min: null,
        source_platform: 'android_health_connect',
      };

      await syncHealthData(patientId, payload);

      setSyncStatus('success');
      setLastSync(new Date().toLocaleTimeString('fr-FR'));
      Alert.alert(
        'Synchronisation reussie',
        'Vos donnees de sante ont ete envoyees au serveur.',
      );
    } catch (error: any) {
      console.error('Erreur de synchronisation:', error);
      setSyncStatus('error');
      Alert.alert(
        'Erreur de synchronisation',
        error.message || 'Impossible d\'envoyer les donnees.',
      );
    } finally {
      setSyncing(false);
    }
  };

  // =====================================================================
  // ECRAN DE CONNEXION
  // =====================================================================

  if (!loggedIn) {
    return (
      <SafeAreaProvider>
        <SafeAreaView style={styles.container}>
          <ScrollView contentContainerStyle={styles.scrollContainer}>
            <View style={styles.card}>
              <Text style={styles.loginIcon}>🏥</Text>
              <Text style={styles.title}>Mood-IoT</Text>
              <Text style={styles.subtitle}>Application Patient</Text>

              <TextInput
                style={styles.input}
                placeholder="Adresse email"
                placeholderTextColor="#999"
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
              />
              <TextInput
                style={styles.input}
                placeholder="Mot de passe"
                placeholderTextColor="#999"
                value={password}
                onChangeText={setPassword}
                secureTextEntry
              />

              <TouchableOpacity
                style={[styles.button, styles.btnPrimary]}
                onPress={handleLogin}
                disabled={authLoading}>
                {authLoading ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.buttonText}>SE CONNECTER</Text>
                )}
              </TouchableOpacity>
            </View>
          </ScrollView>
        </SafeAreaView>
      </SafeAreaProvider>
    );
  }

  // =====================================================================
  // ECRAN PRINCIPAL (authentifie)
  // =====================================================================

  return (
    <SafeAreaProvider>
      <SafeAreaView style={styles.container}>
        <ScrollView contentContainerStyle={styles.scrollContainer}>
          <View style={styles.card}>
            {/* Header */}
            <View style={styles.header}>
              <View>
                <Text style={styles.title}>Mood-IoT</Text>
                <Text style={styles.welcomeText}>Bonjour, {userName}</Text>
              </View>
              <TouchableOpacity onPress={handleLogout}>
                <Text style={styles.logoutText}>Deconnexion</Text>
              </TouchableOpacity>
            </View>

            {/* GPS */}
            <View style={styles.locationBadge}>
              <Text style={styles.locationText}>
                {location
                  ? `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`
                  : 'Localisation...'}
              </Text>
            </View>

            {/* Stats */}
            <View style={styles.statsGrid}>
              <View style={styles.statBox}>
                <Text style={styles.statLabel}>PAS</Text>
                <Text style={styles.statValue}>{steps}</Text>
              </View>

              <View style={styles.statBox}>
                <Text style={styles.statLabel}>BPM</Text>
                <Text style={[styles.statValue, { color: '#e74c3c' }]}>
                  {heartRate}
                </Text>
              </View>

              <View style={styles.statBox}>
                <Text style={styles.statLabel}>SOMMEIL</Text>
                <Text style={[styles.statValue, { color: '#9b59b6', fontSize: 24 }]}>
                  {sleepDisplay}
                </Text>
              </View>
            </View>

            {/* Sync status */}
            {syncStatus !== 'idle' && (
              <View
                style={[
                  styles.statusBadge,
                  syncStatus === 'success' ? styles.statusSuccess : styles.statusError,
                ]}>
                <Text style={styles.statusText}>
                  {syncStatus === 'success'
                    ? `Synchronise a ${lastSync}`
                    : 'Echec de synchronisation'}
                </Text>
              </View>
            )}

            {/* Boutons */}
            <View style={styles.buttonGroup}>
              <TouchableOpacity
                style={[styles.button, styles.btnPrimary]}
                onPress={fetchAndSyncHealthData}
                disabled={syncing}>
                {syncing ? (
                  <View style={styles.syncingRow}>
                    <ActivityIndicator color="#fff" size="small" />
                    <Text style={[styles.buttonText, { marginLeft: 8 }]}>
                      SYNCHRONISATION...
                    </Text>
                  </View>
                ) : (
                  <Text style={styles.buttonText}>SYNCHRONISER</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.button, styles.btnSecondary]}
                onPress={() => HealthConnect.openHealthConnectSettings()}>
                <Text style={styles.buttonText}>REGLAGES SANTE</Text>
              </TouchableOpacity>
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </SafeAreaProvider>
  );
};

// =====================================================================
// STYLES
// =====================================================================

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f0f2f5' },
  scrollContainer: { flexGrow: 1, justifyContent: 'center', padding: 15 },
  card: {
    backgroundColor: 'white',
    borderRadius: 30,
    padding: 20,
    alignItems: 'center',
    elevation: 8,
    shadowColor: '#000',
    shadowOpacity: 0.1,
  },

  // Login
  loginIcon: { fontSize: 48, marginBottom: 8 },
  subtitle: { fontSize: 14, color: '#636e72', marginBottom: 24 },
  input: {
    width: '100%',
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 15,
    color: '#333',
    marginBottom: 12,
  },

  // Header
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    width: '100%',
    marginBottom: 16,
  },
  welcomeText: { fontSize: 14, color: '#636e72', marginTop: 2 },
  logoutText: { fontSize: 13, color: '#e74c3c', fontWeight: '600' },

  // Common
  title: { fontSize: 22, fontWeight: '900', color: '#1a1a1a', marginBottom: 4 },
  locationBadge: {
    backgroundColor: '#f8f9fa',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 20,
    marginBottom: 20,
  },
  locationText: { fontSize: 11, color: '#636e72', fontFamily: 'monospace' },
  statsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
    marginBottom: 20,
  },
  statBox: { flex: 1, alignItems: 'center' },
  statLabel: {
    fontSize: 10,
    color: '#8e8e93',
    fontWeight: 'bold',
    marginBottom: 5,
  },
  statValue: { fontSize: 32, fontWeight: '900', color: '#2ecc71' },

  // Sync status
  statusBadge: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 12,
    marginBottom: 16,
    width: '100%',
    alignItems: 'center',
  },
  statusSuccess: { backgroundColor: '#d4edda' },
  statusError: { backgroundColor: '#f8d7da' },
  statusText: { fontSize: 13, fontWeight: '600', color: '#333' },

  // Buttons
  buttonGroup: { width: '100%' },
  button: {
    paddingVertical: 15,
    borderRadius: 15,
    alignItems: 'center',
    marginBottom: 10,
  },
  btnPrimary: { backgroundColor: '#007AFF' },
  btnSecondary: { backgroundColor: '#636e72' },
  buttonText: { color: 'white', fontWeight: '800', fontSize: 13 },
  syncingRow: { flexDirection: 'row', alignItems: 'center' },
});

export default App;
