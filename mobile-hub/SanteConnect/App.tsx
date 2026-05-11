import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  Platform,
  ScrollView,
  PermissionsAndroid,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import Geolocation from 'react-native-geolocation-service';
import * as HealthConnect from 'react-native-health-connect';

import LoginScreen from './src/screens/LoginScreen';
import { authService } from './src/services/auth';

// ---------------------------------------------------------------------------
// Main health hub screen (existing functionality)
// ---------------------------------------------------------------------------

interface HomeScreenProps {
  onLogout: () => void;
}

const HomeScreen: React.FC<HomeScreenProps> = ({ onLogout }) => {
  const [steps, setSteps] = useState('--');
  const [heartRate, setHeartRate] = useState('--');
  const [sleep, setSleep] = useState('--');
  const [location, setLocation] = useState<{latitude: number; longitude: number} | null>(null);

  const isAndroid = Platform.OS === 'android';

  const formatSleepDuration = (startTime: string, endTime: string) => {
    const durationMs = new Date(endTime).getTime() - new Date(startTime).getTime();
    const totalMinutes = Math.floor(durationMs / (1000 * 60));
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return `${hours}h ${minutes}m`;
  };

  const fetchLocation = async () => {
    if (Platform.OS === 'android') {
      const granted = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
      );
      if (granted !== PermissionsAndroid.RESULTS.GRANTED) {
        return;
      }
    }

    Geolocation.getCurrentPosition(
      (position) => {
        setLocation({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      (error) => console.log('Erreur GPS:', error.message),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 10000 },
    );
  };

  const fetchHealthData = async () => {
    if (!isAndroid) {
      return;
    }

    try {
      await HealthConnect.initialize();

      await HealthConnect.requestPermission([
        { accessType: 'read', recordType: 'Steps' },
        { accessType: 'read', recordType: 'HeartRate' },
        { accessType: 'read', recordType: 'SleepSession' },
      ]);

      const now = new Date();
      const startTimeToday = new Date();
      startTimeToday.setHours(0, 0, 0, 0);

      const stepAggregation = await HealthConnect.aggregateRecord({
        recordType: 'Steps',
        timeRangeFilter: {
          operator: 'between',
          startTime: startTimeToday.toISOString(),
          endTime: now.toISOString(),
        },
      });
      setSteps(String(stepAggregation?.COUNT_TOTAL || 0));

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
        setHeartRate(String(Math.round(bpm) || '--'));
      }

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
        setSleep(formatSleepDuration(lastNight.startTime, lastNight.endTime));
      } else {
        setSleep('Zz..');
      }

      fetchLocation();
    } catch (error) {
      console.error('Erreur de synchronisation:', error);
    }
  };

  const handleLogout = async () => {
    await authService.logout();
    onLogout();
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContainer}>
        <View style={styles.card}>
          <Text style={styles.title}>Android | Mood IoT Hub</Text>

          <View style={styles.locationBadge}>
            <Text style={styles.locationText}>
              {location
                ? `${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`
                : 'Localisation...'}
            </Text>
          </View>

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
              <Text style={styles.statLabel}>Temps de sommeil</Text>
              <Text
                style={[styles.statValue, { color: '#9b59b6', fontSize: 24 }]}
              >
                {sleep}
              </Text>
            </View>
          </View>

          <View style={styles.buttonGroup}>
            <TouchableOpacity
              style={[styles.button, styles.btnPrimary]}
              onPress={fetchHealthData}
            >
              <Text style={styles.buttonText}>TOUT SYNCHRONISER</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.button, styles.btnSecondary]}
              onPress={() => HealthConnect.openHealthConnectSettings()}
            >
              <Text style={styles.buttonText}>REGLAGES SANTE</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.button, styles.btnLogout]}
              onPress={handleLogout}
            >
              <Text style={styles.buttonText}>DECONNEXION</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

// ---------------------------------------------------------------------------
// Root App with auth guard
// ---------------------------------------------------------------------------

const App = () => {
  const [isReady, setIsReady] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      const authenticated = await authService.isAuthenticated();
      setIsLoggedIn(authenticated);
      setIsReady(true);
    };
    checkAuth();
  }, []);

  if (!isReady) {
    return (
      <SafeAreaProvider>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#0066CC" />
        </View>
      </SafeAreaProvider>
    );
  }

  return (
    <SafeAreaProvider>
      {isLoggedIn ? (
        <HomeScreen onLogout={() => setIsLoggedIn(false)} />
      ) : (
        <LoginScreen onLoginSuccess={() => setIsLoggedIn(true)} />
      )}
    </SafeAreaProvider>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f0f2f5',
  },
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
  title: {
    fontSize: 22,
    fontWeight: '900',
    color: '#1a1a1a',
    marginBottom: 10,
  },
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
    marginBottom: 30,
  },
  statBox: { flex: 1, alignItems: 'center' },
  statLabel: {
    fontSize: 10,
    color: '#8e8e93',
    fontWeight: 'bold',
    marginBottom: 5,
  },
  statValue: { fontSize: 32, fontWeight: '900', color: '#2ecc71' },
  buttonGroup: { width: '100%' },
  button: {
    paddingVertical: 15,
    borderRadius: 15,
    alignItems: 'center',
    marginBottom: 10,
  },
  btnPrimary: { backgroundColor: '#007AFF' },
  btnSecondary: { backgroundColor: '#636e72' },
  btnLogout: { backgroundColor: '#E53E3E' },
  buttonText: { color: 'white', fontWeight: '800', fontSize: 13 },
});

export default App;
