import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, StyleSheet,
  TouchableOpacity, ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuthStore } from '../store/authStore';

// ────────────────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────────────────

interface Baselines {
  heart_rate_avg: number;
  sleep_duration_min: number;
  step_count: number;
  screen_time_min: number;
  heart_rate_variability: number;
  sleep_quality_score: number;
}

interface DayMetrics {
  patient_id: string;
  date: string;
  heart_rate_avg: number | null;
  heart_rate_variability: number | null;
  sleep_duration_min: number | null;
  sleep_quality_score: number | null;
  step_count: number | null;
  screen_time_min: number | null;
  gps_radius_km: number | null;
  call_count: number | null;
  call_duration_min: number | null;
  baselines: Baselines;
}

// ────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────

function fmtSteps(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(Math.round(n));
}

function fmtHours(min: number): string {
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return m > 0 ? `${h}h${m.toString().padStart(2, '0')}` : `${h}h`;
}

function fmtBpm(bpm: number): string {
  return `${Math.round(bpm)}`;
}

function fmtScore(score: number): string {
  return `${Math.round(score)}/100`;
}

/** Δ% par rapport à la baseline, positif = au-dessus */
function delta(value: number, baseline: number): number {
  if (baseline === 0) return 0;
  return Math.round(((value - baseline) / baseline) * 100);
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long',
  });
}

// ────────────────────────────────────────────────────────────────────────────
// MetricCard
// ────────────────────────────────────────────────────────────────────────────

interface MetricCardProps {
  icon: string;
  name: string;
  value: string;
  unit: string;
  alert?: boolean;
  trendLabel?: string;
  baseline?: string;
}

function MetricCard({ icon, name, value, unit, alert, trendLabel, baseline }: MetricCardProps) {
  return (
    <View style={[s.metricCard, alert && s.metricCardAlert]}>
      <Text style={s.metricIcon}>{icon}</Text>
      <Text style={s.metricName}>{name}</Text>
      <Text style={[s.metricValue, alert && s.metricValueAlert]}>{value}</Text>
      <Text style={s.metricUnit}>{unit}</Text>
      {trendLabel && (
        <View style={[s.trendBadge, alert ? s.trendBadgeAlert : s.trendBadgeOk]}>
          <Text style={[s.trendText, alert ? s.trendTextAlert : s.trendTextOk]}>{trendLabel}</Text>
        </View>
      )}
      {baseline && (
        <Text style={s.baselineText}>Base : {baseline}</Text>
      )}
    </View>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// BarChart
// ────────────────────────────────────────────────────────────────────────────

interface BarChartProps {
  title: string;
  data: { label: string; value: number; displayValue: string }[];
  max: number;
  colorFn: (v: number) => string;
}

function BarChart({ title, data, max, colorFn }: BarChartProps) {
  return (
    <View style={s.chartCard}>
      <Text style={s.chartTitle}>{title}</Text>
      <View style={s.barChart}>
        {data.map((d, i) => (
          <View key={i} style={s.barCol}>
            <View style={s.barTrack}>
              <View style={[s.barFill, {
                height: `${Math.min((d.value / max) * 100, 100)}%` as any,
                backgroundColor: colorFn(d.value),
              }]} />
            </View>
            <Text style={s.barLabel}>{d.label}</Text>
            <Text style={s.barVal}>{d.displayValue}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Écran principal
// ────────────────────────────────────────────────────────────────────────────

const API_BASE = 'https://api.mood-iot.fr/api/v1';

export default function Mesures() {
  const { user, getValidAccessToken } = useAuthStore();

  const [metrics, setMetrics]     = useState<DayMetrics | null>(null);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError]         = useState<string | null>(null);

  const fetchMetrics = useCallback(async (isRefresh = false) => {
    if (!user?.patient_id) return;
    isRefresh ? setRefreshing(true) : setLoading(true);
    setError(null);
    try {
      const token = await getValidAccessToken();
      if (!token) throw new Error('Session expirée');

      const res = await fetch(`${API_BASE}/patients/${user.patient_id ?? user.id}/metrics`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Erreur serveur (${res.status})`);

      const data: DayMetrics = await res.json();
      setMetrics(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Impossible de charger les données');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?.patient_id]);

  useEffect(() => { fetchMetrics(); }, [fetchMetrics]);

  // ── Derived values ────────────────────────────────────────────────────────

  const b = metrics?.baselines;

  const steps     = metrics?.step_count ?? null;
  const sleepMin  = metrics?.sleep_duration_min ?? null;
  const hr        = metrics?.heart_rate_avg ?? null;
  const hrv       = metrics?.heart_rate_variability ?? null;
  const sleepQual = metrics?.sleep_quality_score ?? null;
  const screenMin = metrics?.screen_time_min ?? null;
  const calls     = metrics?.call_count ?? null;

  const stepsAlert  = steps  !== null && b ? steps  < b.step_count  * 0.7  : false;
  const sleepAlert  = sleepMin !== null && b ? sleepMin < b.sleep_duration_min * 0.8 : false;
  const hrAlert     = hr    !== null && hr > 100;
  const screenAlert = screenMin !== null && b ? screenMin > b.screen_time_min * 1.3 : false;
  const qualAlert   = sleepQual !== null && sleepQual < 40;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      {/* Header */}
      <View style={s.header}>
        <Text style={s.greeting}>
          {metrics ? formatDate(metrics.date) : 'Chargement…'}
        </Text>
        <Text style={s.title}>Mes mesures</Text>
      </View>

      {loading && (
        <View style={s.loaderCenter}>
          <ActivityIndicator color="#2D7D6E" size="large" />
          <Text style={s.loaderText}>Récupération des données…</Text>
        </View>
      )}

      {!loading && (
        <ScrollView
          contentContainerStyle={s.scroll}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => fetchMetrics(true)}
              tintColor="#2D7D6E"
              colors={['#2D7D6E']}
              title="Mise à jour…"
              titleColor="#5B7672"
            />
          }
        >
          {/* Erreur */}
          {error && (
            <View style={s.errorBox}>
              <Text style={s.errorText}>⚠️ {error}</Text>
              <TouchableOpacity onPress={() => fetchMetrics()} style={{ marginTop: 6 }}>
                <Text style={[s.errorText, { textDecorationLine: 'underline' }]}>Réessayer</Text>
              </TouchableOpacity>
            </View>
          )}

          {/* Grille de métriques */}
          {metrics && (
            <>
              <Text style={s.sectionLabel}>Activité & sommeil</Text>
              <View style={s.grid}>
                <MetricCard
                  icon="🚶"
                  name="Pas"
                  value={steps !== null ? fmtSteps(steps) : '—'}
                  unit="pas aujourd'hui"
                  alert={stepsAlert}
                  trendLabel={
                    steps !== null && b
                      ? stepsAlert
                        ? `↓ ${Math.abs(delta(steps, b.step_count))}% sous la base`
                        : `✓ ${delta(steps, b.step_count) >= 0 ? '+' : ''}${delta(steps, b.step_count)}% vs base`
                      : undefined
                  }
                  baseline={b ? fmtSteps(b.step_count) + ' pas' : undefined}
                />
                <MetricCard
                  icon="😴"
                  name="Sommeil"
                  value={sleepMin !== null ? fmtHours(sleepMin) : '—'}
                  unit="cette nuit"
                  alert={sleepAlert}
                  trendLabel={
                    sleepMin !== null && b
                      ? sleepAlert
                        ? `↓ ${Math.abs(delta(sleepMin, b.sleep_duration_min))}% sous la base`
                        : `✓ Repos suffisant`
                      : undefined
                  }
                  baseline={b ? fmtHours(b.sleep_duration_min) : undefined}
                />
                <MetricCard
                  icon="⭐"
                  name="Qualité sommeil"
                  value={sleepQual !== null ? fmtScore(sleepQual) : '—'}
                  unit="score"
                  alert={qualAlert}
                  trendLabel={
                    sleepQual !== null && b
                      ? qualAlert
                        ? `↓ ${Math.abs(delta(sleepQual, b.sleep_quality_score))}% sous la base`
                        : `✓ Qualité correcte`
                      : undefined
                  }
                  baseline={b ? fmtScore(b.sleep_quality_score) : undefined}
                />
                <MetricCard
                  icon="📱"
                  name="Temps d'écran"
                  value={screenMin !== null ? fmtHours(screenMin) : '—'}
                  unit="aujourd'hui"
                  alert={screenAlert}
                  trendLabel={
                    screenMin !== null && b
                      ? screenAlert
                        ? `↑ ${delta(screenMin, b.screen_time_min)}% au-dessus`
                        : `✓ Dans la norme`
                      : undefined
                  }
                  baseline={b ? fmtHours(b.screen_time_min) : undefined}
                />
              </View>

              <Text style={s.sectionLabel}>Cardiaque</Text>
              <View style={s.grid}>
                <MetricCard
                  icon="❤️"
                  name="Fréquence cardiaque"
                  value={hr !== null ? fmtBpm(hr) : '—'}
                  unit="bpm moyen"
                  alert={hrAlert}
                  trendLabel={
                    hr !== null && b
                      ? hrAlert
                        ? `↑ Au-dessus de la normale`
                        : `✓ ${delta(hr, b.heart_rate_avg) >= 0 ? '+' : ''}${delta(hr, b.heart_rate_avg)}% vs base`
                      : undefined
                  }
                  baseline={b ? `${Math.round(b.heart_rate_avg)} bpm` : undefined}
                />
                <MetricCard
                  icon="💓"
                  name="Variabilité (HRV)"
                  value={hrv !== null ? `${Math.round(hrv)} ms` : '—'}
                  unit="ms"
                  alert={false}
                  trendLabel={
                    hrv !== null && b
                      ? `${delta(hrv, b.heart_rate_variability) >= 0 ? '+' : ''}${delta(hrv, b.heart_rate_variability)}% vs base`
                      : undefined
                  }
                  baseline={b ? `${Math.round(b.heart_rate_variability)} ms` : undefined}
                />
              </View>

              <Text style={s.sectionLabel}>Social</Text>
              <View style={s.grid}>
                <MetricCard
                  icon="📞"
                  name="Appels"
                  value={calls !== null ? String(calls) : '—'}
                  unit="appel(s) aujourd'hui"
                />
                {metrics.call_duration_min !== null && (
                  <MetricCard
                    icon="🕐"
                    name="Durée appels"
                    value={fmtHours(metrics.call_duration_min)}
                    unit="au total"
                  />
                )}
                {metrics.gps_radius_km !== null && (
                  <MetricCard
                    icon="📍"
                    name="Rayon GPS"
                    value={`${metrics.gps_radius_km.toFixed(1)} km`}
                    unit="périmètre parcouru"
                  />
                )}
              </View>

              {/* Barres de comparaison baseline */}
              {b && (
                <>
                  <BarChart
                    title="😴 Sommeil vs baseline (min)"
                    data={[
                      { label: 'Aujourd\'hui', value: sleepMin ?? 0, displayValue: sleepMin ? fmtHours(sleepMin) : '—' },
                      { label: 'Baseline',     value: b.sleep_duration_min, displayValue: fmtHours(b.sleep_duration_min) },
                    ]}
                    max={Math.max((sleepMin ?? 0), b.sleep_duration_min) * 1.2}
                    colorFn={(v) => v < b.sleep_duration_min * 0.8 ? '#C45850' : '#2D7D6E'}
                  />
                  <BarChart
                    title="🚶 Pas vs baseline"
                    data={[
                      { label: 'Aujourd\'hui', value: steps ?? 0, displayValue: steps ? fmtSteps(steps) : '—' },
                      { label: 'Baseline',     value: b.step_count, displayValue: fmtSteps(b.step_count) },
                    ]}
                    max={Math.max((steps ?? 0), b.step_count) * 1.2}
                    colorFn={(v) => v < b.step_count * 0.7 ? '#C45850' : '#2D7D6E'}
                  />
                </>
              )}
            </>
          )}

          <View style={s.note}>
            <Text style={s.noteText}>
              ℹ️ Données transmises par votre dispositif et analysées par votre médecin. Glissez vers le bas pour actualiser.
            </Text>
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Styles
// ────────────────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  root:    { flex: 1, backgroundColor: '#F4FAF8' },
  header:  { backgroundColor: '#fff', paddingHorizontal: 20, paddingTop: 16, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: '#DCEAE5' },
  greeting:{ fontSize: 12, color: '#5B7672', fontWeight: '500', textTransform: 'capitalize' },
  title:   { fontSize: 21, fontWeight: '700', color: '#1B3A3A', marginTop: 2 },

  loaderCenter: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  loaderText:   { fontSize: 13, color: '#2D7D6E', fontWeight: '600' },

  scroll:       { padding: 16, paddingBottom: 40 },
  sectionLabel: { fontSize: 11, fontWeight: '700', color: '#5B7672', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 10, marginTop: 4 },

  errorBox:  { backgroundColor: '#FBEAE8', borderRadius: 12, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: '#F4B8B0' },
  errorText: { fontSize: 12, color: '#C45850', fontWeight: '600' },

  grid:         { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 16 },
  metricCard:   { width: '47%', backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#DCEAE5', alignItems: 'center' },
  metricCardAlert: { borderColor: '#C45850', borderWidth: 1.5 },
  metricIcon:   { fontSize: 26, marginBottom: 6 },
  metricName:   { fontSize: 11, color: '#5B7672', fontWeight: '600', marginBottom: 4, textAlign: 'center' },
  metricValue:  { fontSize: 26, fontWeight: '700', color: '#1B3A3A' },
  metricValueAlert: { color: '#C45850' },
  metricUnit:   { fontSize: 11, color: '#5B7672', marginTop: 2, textAlign: 'center' },
  baselineText: { fontSize: 10, color: '#A3B8B5', marginTop: 4 },

  trendBadge:      { marginTop: 6, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  trendBadgeAlert: { backgroundColor: '#FBEAE8' },
  trendBadgeOk:    { backgroundColor: '#EBF8F4' },
  trendText:       { fontSize: 10, fontWeight: '700' },
  trendTextAlert:  { color: '#C45850' },
  trendTextOk:     { color: '#2D7D6E' },

  chartCard:  { backgroundColor: '#fff', borderRadius: 18, padding: 16, borderWidth: 1, borderColor: '#DCEAE5', marginBottom: 12 },
  chartTitle: { fontSize: 13, fontWeight: '700', color: '#1B3A3A', marginBottom: 16 },
  barChart:   { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-around', height: 100 },
  barCol:     { flex: 1, alignItems: 'center' },
  barTrack:   { width: 36, height: 80, backgroundColor: '#F4FAF8', borderRadius: 8, justifyContent: 'flex-end', overflow: 'hidden' },
  barFill:    { width: '100%', borderRadius: 8 },
  barLabel:   { fontSize: 11, color: '#5B7672', marginTop: 6, textAlign: 'center' },
  barVal:     { fontSize: 10, color: '#1B3A3A', fontWeight: '600', marginTop: 2 },

  note:     { backgroundColor: '#E8F3EF', borderRadius: 14, padding: 14, marginTop: 4 },
  noteText: { fontSize: 12, color: '#2D7D6E', lineHeight: 18 },
});