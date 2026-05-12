/**
 * Mood-IoT : Ecran de consentement RGPD (premier lancement).
 *
 * Affiche les conditions d'utilisation et demande le consentement
 * explicite du patient avant la collecte de donnees de sante.
 */

import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
  Switch,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ConsentScreenProps {
  onConsentGiven: () => void;
}

interface ConsentItem {
  id: string;
  label: string;
  description: string;
  required: boolean;
}

// ---------------------------------------------------------------------------
// Consent items
// ---------------------------------------------------------------------------

const CONSENT_ITEMS: ConsentItem[] = [
  {
    id: 'health_data',
    label: 'Collecte de donnees de sante',
    description:
      'Nous collectons vos donnees de sante (frequence cardiaque, sommeil, activite physique) pour le suivi psychiatrique.',
    required: true,
  },
  {
    id: 'geolocation',
    label: 'Donnees de geolocalisation',
    description:
      'Votre position GPS est utilisee pour evaluer votre mobilite quotidienne, un indicateur de bien-etre.',
    required: true,
  },
  {
    id: 'ai_analysis',
    label: 'Analyse par intelligence artificielle',
    description:
      'Vos donnees sont analysees par un algorithme de scoring pour detecter des signaux de risque et generer des recommandations.',
    required: true,
  },
  {
    id: 'notifications',
    label: 'Notifications et coaching',
    description:
      'Recevez des messages de coaching personnalises et des alertes de bien-etre.',
    required: false,
  },
  {
    id: 'data_sharing',
    label: 'Partage avec votre psychiatre',
    description:
      'Vos scores et alertes sont partages avec votre psychiatre referent pour un meilleur suivi.',
    required: true,
  },
];

const STORAGE_KEY = '@mood_iot_consent_given';

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const ConsentScreen: React.FC<ConsentScreenProps> = ({ onConsentGiven }) => {
  const [consents, setConsents] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    CONSENT_ITEMS.forEach((item) => {
      initial[item.id] = item.required;
    });
    return initial;
  });

  const allRequiredAccepted = CONSENT_ITEMS.filter((c) => c.required).every(
    (c) => consents[c.id],
  );

  const handleToggle = (id: string, required: boolean) => {
    if (required) return;
    setConsents((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleAccept = async () => {
    if (!allRequiredAccepted) {
      Alert.alert(
        'Consentements requis',
        'Veuillez accepter tous les consentements obligatoires pour continuer.',
      );
      return;
    }

    try {
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify({
        consents,
        accepted_at: new Date().toISOString(),
        version: '1.0',
      }));
      onConsentGiven();
    } catch (error) {
      Alert.alert('Erreur', 'Impossible de sauvegarder le consentement.');
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.logo}>🛡️</Text>
          <Text style={styles.title}>Protection de vos donnees</Text>
          <Text style={styles.subtitle}>
            Conformement au RGPD (Reglement General sur la Protection des Donnees),
            nous avons besoin de votre consentement explicite avant de collecter
            vos donnees de sante.
          </Text>
        </View>

        {/* Consent items */}
        {CONSENT_ITEMS.map((item) => (
          <View key={item.id} style={styles.consentCard}>
            <View style={styles.consentHeader}>
              <View style={styles.consentLabelRow}>
                <Text style={styles.consentLabel}>{item.label}</Text>
                {item.required && (
                  <View style={styles.requiredBadge}>
                    <Text style={styles.requiredText}>Obligatoire</Text>
                  </View>
                )}
              </View>
              <Switch
                value={consents[item.id]}
                onValueChange={() => handleToggle(item.id, item.required)}
                disabled={item.required}
                trackColor={{ false: '#E2E8F0', true: '#90CDF4' }}
                thumbColor={consents[item.id] ? '#0066CC' : '#CBD5E0'}
              />
            </View>
            <Text style={styles.consentDescription}>{item.description}</Text>
          </View>
        ))}

        {/* Rights info */}
        <View style={styles.rightsCard}>
          <Text style={styles.rightsTitle}>Vos droits</Text>
          <Text style={styles.rightsText}>
            • Droit d'acces et de portabilite (Art. 15 & 20){'\n'}
            • Droit de rectification (Art. 16){'\n'}
            • Droit a l'effacement (Art. 17){'\n'}
            • Droit de retirer votre consentement a tout moment{'\n'}
            • Contact DPO : dpo@mood-iot.fr
          </Text>
        </View>

        {/* Accept button */}
        <TouchableOpacity
          style={[
            styles.acceptButton,
            !allRequiredAccepted && styles.acceptButtonDisabled,
          ]}
          onPress={handleAccept}
          disabled={!allRequiredAccepted}
        >
          <Text style={styles.acceptButtonText}>
            J'accepte et je continue
          </Text>
        </TouchableOpacity>

        <Text style={styles.footerText}>
          Vous pouvez modifier vos preferences a tout moment dans les parametres
          de l'application.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F7FAFC',
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
  },
  logo: {
    fontSize: 48,
    marginBottom: 12,
  },
  title: {
    fontSize: 24,
    fontWeight: '800',
    color: '#1A202C',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#718096',
    textAlign: 'center',
    lineHeight: 20,
  },
  consentCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 2 },
  },
  consentHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  consentLabelRow: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 12,
  },
  consentLabel: {
    fontSize: 15,
    fontWeight: '700',
    color: '#2D3748',
    marginRight: 8,
  },
  requiredBadge: {
    backgroundColor: '#FED7D7',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  requiredText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#E53E3E',
  },
  consentDescription: {
    fontSize: 13,
    color: '#718096',
    lineHeight: 18,
  },
  rightsCard: {
    backgroundColor: '#EBF8FF',
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
    marginBottom: 24,
  },
  rightsTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#2B6CB0',
    marginBottom: 8,
  },
  rightsText: {
    fontSize: 13,
    color: '#2C5282',
    lineHeight: 20,
  },
  acceptButton: {
    backgroundColor: '#0066CC',
    paddingVertical: 16,
    borderRadius: 14,
    alignItems: 'center',
    marginBottom: 12,
  },
  acceptButtonDisabled: {
    backgroundColor: '#A0AEC0',
  },
  acceptButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '800',
  },
  footerText: {
    fontSize: 12,
    color: '#A0AEC0',
    textAlign: 'center',
    lineHeight: 18,
  },
});

export default ConsentScreen;
