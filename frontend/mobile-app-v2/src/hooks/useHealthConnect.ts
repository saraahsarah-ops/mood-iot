/**
 * Hook useHealthConnect
 * - Sépare "refreshing" (pull-to-refresh) de "loading" (chargement initial)
 * - Écoute AppState pour re-fetcher au retour depuis Health Connect
 * - Ne re-demande pas les permissions si déjà accordées
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import {
  initHealthConnect,
  fetchDailyMetrics,
  fetchWeeklyData,
  checkHealthConnectStatus,
  checkGrantedPermissions,
  DailyMetrics,
  WeeklyPoint,
  HealthConnectStatus,
} from '../services/healthConnect';

interface UseHealthConnectResult {
  status: HealthConnectStatus | 'loading' | 'denied';
  daily: DailyMetrics | null;
  weekly: WeeklyPoint[];
  loading: boolean;      // chargement initial uniquement
  refreshing: boolean;   // pull-to-refresh uniquement
  error: string | null;
  refresh: () => Promise<void>;
}

export function useHealthConnect(): UseHealthConnectResult {
  const [status, setStatus]       = useState<HealthConnectStatus | 'loading' | 'denied'>('loading');
  const [daily, setDaily]         = useState<DailyMetrics | null>(null);
  const [weekly, setWeekly]       = useState<WeeklyPoint[]>([]);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]         = useState<string | null>(null);

  const isInitialized = useRef(false);
  const appState      = useRef(AppState.currentState);

  // Fetch données uniquement (permissions déjà vérifiées)
  const fetchData = useCallback(async () => {
    setError(null);
    try {
      const [d, w] = await Promise.all([fetchDailyMetrics(), fetchWeeklyData()]);
      setDaily(d);
      setWeekly(w);
      setStatus('ready');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur lors de la lecture des données');
    }
  }, []);

  // Init complète (première fois ou après refus de permissions)
  const init = useCallback(async () => {
    setError(null);
    try {
      const hcStatus = await checkHealthConnectStatus();
      if (hcStatus !== 'ready') {
        setStatus(hcStatus);
        return;
      }
      const granted = await initHealthConnect();
      if (!granted) {
        setStatus('denied');
        return;
      }
      await fetchData();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur Health Connect');
    }
  }, [fetchData]);

  // Chargement initial
  useEffect(() => {
    (async () => {
      setLoading(true);
      await init();
      setLoading(false);
      isInitialized.current = true;
    })();
  }, [init]);

  // Écoute AppState — re-fetch silencieux au retour dans l'app
  useEffect(() => {
    const subscription = AppState.addEventListener('change', async (nextState: AppStateStatus) => {
      if (
        appState.current.match(/inactive|background/) &&
        nextState === 'active' &&
        isInitialized.current
      ) {
        // L'user revient peut-être depuis HC settings → vérifie les permissions silencieusement
        const hasPermissions = await checkGrantedPermissions();
        if (hasPermissions) {
          await fetchData();
          setStatus('ready');
        } else if (status === 'ready') {
          // Permissions révoquées pendant qu'on était en arrière-plan
          setStatus('denied');
        }
      }
      appState.current = nextState;
    });
    return () => subscription.remove();
  }, [fetchData, status]);

  // Pull-to-refresh : re-fetch données si permissions ok, sinon re-init
  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      if (status === 'ready') {
        await fetchData();
      } else {
        await init();
      }
    } finally {
      setRefreshing(false);
    }
  }, [status, fetchData, init]);

  return { status, daily, weekly, loading, refreshing, error, refresh };
}