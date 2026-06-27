import React, { useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet, Alert
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

interface Slot {
  id: string;
  when: string;
  with: string;
  urgent?: boolean;
  confirmed?: boolean;
}

interface BookedRDV {
  id: string;
  when: string;
  with: string;
  type: 'Téléconsultation';
}

const URGENT_SLOTS: Slot[] = [
  { id: 'u1', when: "Aujourd'hui · 10:30", with: 'Sous 2h · Dr. Martin', urgent: true },
];

const OTHER_SLOTS: Slot[] = [
  { id: 's1', when: 'Demain · 09:00', with: 'Dr. Martin' },
  { id: 's2', when: 'Demain · 14:30', with: 'Dr. Martin' },
  { id: 's3', when: 'Jeudi · 11:00', with: 'Dr. Martin' },
  { id: 's4', when: 'Vendredi · 16:00', with: 'Dr. Martin' },
];

const BOOKED: BookedRDV[] = [
  { id: 'b1', when: 'Mar. 17 juin · 14:00', with: 'Dr. Martin', type: 'Téléconsultation' },
  { id: 'b2', when: 'Mer. 4 juin · 10:00', with: 'Dr. Martin', type: 'Téléconsultation' },
];

export default function RDV() {
  const [confirmed, setConfirmed] = useState<string | null>(null);

  const handleConfirm = (slot: Slot) => {
    Alert.alert(
      'Confirmer le rendez-vous ?',
      `${slot.when} avec ${slot.with}`,
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Confirmer',
          style: 'default',
          onPress: () => setConfirmed(slot.id),
        },
      ]
    );
  };

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <View style={s.header}>
        <Text style={s.greeting}>Téléconsultation</Text>
        <Text style={s.title}>Prendre rendez-vous</Text>
      </View>

      <ScrollView contentContainerStyle={s.scroll}>

        {/* Bannière urgence */}
        <View style={s.banner}>
          <Text style={{ fontSize: 20 }}>⏱️</Text>
          <Text style={s.bannerText}>Un créneau urgent t'a été réservé suite à ton suivi récent.</Text>
        </View>

        {/* Créneaux urgents */}
        <Text style={s.sectionTitle}>Créneau prioritaire</Text>
        {URGENT_SLOTS.map(slot => (
          <SlotRow
            key={slot.id}
            slot={slot}
            confirmed={confirmed === slot.id}
            onPress={() => handleConfirm(slot)}
          />
        ))}

        {/* Autres créneaux */}
        <Text style={s.sectionTitle}>Autres créneaux disponibles</Text>
        {OTHER_SLOTS.map(slot => (
          <SlotRow
            key={slot.id}
            slot={slot}
            confirmed={confirmed === slot.id}
            onPress={() => handleConfirm(slot)}
          />
        ))}

        {/* RDV passés */}
        <Text style={s.sectionTitle}>Historique</Text>
        {BOOKED.map(rdv => (
          <View key={rdv.id} style={s.pastCard}>
            <View style={s.pastLeft}>
              <Text style={s.pastIcon}>🗓️</Text>
              <View>
                <Text style={s.pastWhen}>{rdv.when}</Text>
                <Text style={s.pastWith}>{rdv.type} · {rdv.with}</Text>
              </View>
            </View>
            <View style={s.pastBadge}><Text style={s.pastBadgeText}>Passé</Text></View>
          </View>
        ))}

      </ScrollView>
    </SafeAreaView>
  );
}

function SlotRow({ slot, confirmed, onPress }: { slot: Slot; confirmed: boolean; onPress: () => void }) {
  return (
    <View style={[s.slotCard, slot.urgent && s.slotCardUrgent, confirmed && s.slotCardConfirmed]}>
      <View style={s.slotLeft}>
        <Text style={[s.slotWhen, slot.urgent && s.slotWhenUrgent]}>{slot.when}</Text>
        <Text style={s.slotWith}>{slot.with}</Text>
      </View>
      {confirmed ? (
        <View style={s.confirmedBadge}>
          <Text style={s.confirmedText}>✓ Confirmé</Text>
        </View>
      ) : (
        <TouchableOpacity
          style={[s.slotBtn, slot.urgent && s.slotBtnUrgent]}
          onPress={onPress}
        >
          <Text style={[s.slotBtnText, slot.urgent && s.slotBtnTextUrgent]}>
            {slot.urgent ? 'Confirmer' : 'Choisir'}
          </Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F4FAF8' },
  header: { backgroundColor: '#fff', paddingHorizontal: 20, paddingTop: 16, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: '#DCEAE5' },
  greeting: { fontSize: 12, color: '#5B7672', fontWeight: '500' },
  title: { fontSize: 21, fontWeight: '700', color: '#1B3A3A', marginTop: 2 },
  scroll: { padding: 16, paddingBottom: 32 },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FBEAE8', borderRadius: 14, padding: 14, marginBottom: 20, borderWidth: 1, borderColor: '#C45850' + '44' },
  bannerText: { flex: 1, fontSize: 13, color: '#C45850', fontWeight: '600', lineHeight: 18 },
  sectionTitle: { fontSize: 12, fontWeight: '700', color: '#5B7672', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10, marginTop: 4 },
  slotCard: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#fff', borderRadius: 16, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#DCEAE5' },
  slotCardUrgent: { borderColor: '#C45850', backgroundColor: '#FFFAFA' },
  slotCardConfirmed: { borderColor: '#2D7D6E', backgroundColor: '#F4FAF8' },
  slotLeft: { flex: 1 },
  slotWhen: { fontSize: 14, fontWeight: '700', color: '#1B3A3A' },
  slotWhenUrgent: { color: '#C45850' },
  slotWith: { fontSize: 12, color: '#5B7672', marginTop: 2 },
  slotBtn: { backgroundColor: '#E8F3EF', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8 },
  slotBtnUrgent: { backgroundColor: '#C45850' },
  slotBtnText: { fontSize: 12, fontWeight: '700', color: '#2D7D6E' },
  slotBtnTextUrgent: { color: '#fff' },
  confirmedBadge: { backgroundColor: '#E8F3EF', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 6 },
  confirmedText: { fontSize: 12, fontWeight: '700', color: '#2D7D6E' },
  pastCard: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#fff', borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: '#DCEAE5', opacity: 0.7 },
  pastLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 },
  pastIcon: { fontSize: 20 },
  pastWhen: { fontSize: 13, fontWeight: '600', color: '#1B3A3A' },
  pastWith: { fontSize: 11, color: '#5B7672', marginTop: 2 },
  pastBadge: { backgroundColor: '#F4FAF8', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4 },
  pastBadgeText: { fontSize: 11, color: '#5B7672', fontWeight: '600' },
});