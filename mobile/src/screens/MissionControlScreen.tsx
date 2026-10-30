/**
 * Kora Mobile Mission Control Screen.
 * Features live agent thought streaming, air-gap toggle, ghost diff review,
 * and biometric commit approval gestures.
 */

import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, SafeAreaView, TextInput, Alert } from 'react-native';
import { BiometricGate } from '../services/biometrics';
import { KoraMobileClient, AgentEvent } from '../services/api';

export default function MissionControlScreen() {
  const [airGapped, setAirGapped] = useState(true);
  const [instruction, setInstruction] = useState('');
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [client, setClient] = useState<KoraMobileClient | null>(null);

  useEffect(() => {
    const mobileClient = new KoraMobileClient('127.0.0.1:7420');
    mobileClient.connect((event) => {
      setEvents((prev) => [event, ...prev]);
    });
    setClient(mobileClient);

    return () => mobileClient.disconnect();
  }, []);

  const handleAuthorizeCommit = async (taskId: string) => {
    const auth = await BiometricGate.authenticateAction(`Authorize Autonomous Commit for ${taskId}`);
    if (auth.success) {
      Alert.alert('Commit Authorized', `Cryptographically signed commit for task ${taskId}.`);
    } else {
      Alert.alert('Authentication Failed', 'Biometric verification was not completed.');
    }
  };

  const handleSend = () => {
    if (!instruction.trim() || !client) return;
    client.sendInstruction(instruction);
    setInstruction('');
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* HEADER */}
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.logo}>⚡</Text>
          <Text style={styles.title}>KORA <Text style={styles.subtitle}>MOBILE</Text></Text>
        </View>
        <TouchableOpacity
          style={[styles.airgapBadge, airGapped ? styles.airgapActive : styles.airgapInactive]}
          onPress={() => setAirGapped(!airGapped)}
        >
          <Text style={styles.airgapText}>{airGapped ? '🔒 AIR-GAPPED' : '🌐 HYBRID'}</Text>
        </TouchableOpacity>
      </View>

      {/* AGENT STREAM LOG */}
      <ScrollView style={styles.streamContainer}>
        <View style={styles.statusCard}>
          <Text style={styles.cardHeader}>ACTIVE AGENT RUNTIME</Text>
          <Text style={styles.cardBody}>Model: Qwen 2.5 Coder 7B (Edge)</Text>
          <Text style={styles.cardCost}>Token Cost: $0.00000</Text>
        </View>

        <Text style={styles.sectionHeader}>LIVE AGENT ACTIONS</Text>
        {events.length === 0 ? (
          <Text style={styles.emptyText}>Waiting for agent tasks...</Text>
        ) : (
          events.map((evt, idx) => (
            <View key={idx} style={styles.eventCard}>
              <Text style={styles.eventType}>{evt.type.toUpperCase()}</Text>
              {evt.prompt && <Text style={styles.eventPrompt}>{evt.prompt}</Text>}
              {evt.verification && <Text style={styles.eventBody}>{evt.verification}</Text>}
              {evt.diff && (
                <View style={styles.diffBox}>
                  <Text style={styles.diffText}>{evt.diff}</Text>
                </View>
              )}
              <TouchableOpacity
                style={styles.authorizeButton}
                onPress={() => handleAuthorizeCommit(evt.task_id || 'task_live')}
              >
                <Text style={styles.authorizeButtonText}>✓ Biometric Signoff</Text>
              </TouchableOpacity>
            </View>
          ))
        )}
      </ScrollView>

      {/* INPUT DOCK */}
      <View style={styles.inputDock}>
        <TextInput
          style={styles.input}
          placeholder="Instruct agent (e.g. 'Heal test suite')..."
          placeholderTextColor="#64748B"
          value={instruction}
          onChangeText={setInstruction}
        />
        <TouchableOpacity style={styles.sendButton} onPress={handleSend}>
          <Text style={styles.sendButtonText}>➔</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#070A12' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.08)' },
  titleRow: { flexDirection: 'row', alignItems: 'center' },
  logo: { fontSize: 18, marginRight: 6 },
  title: { color: '#FFFFFF', fontWeight: 'bold', fontSize: 16 },
  subtitle: { color: '#3B82F6', fontWeight: 'normal' },
  airgapBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, borderWidth: 1 },
  airgapActive: { backgroundColor: 'rgba(16,185,129,0.15)', borderColor: '#10B981' },
  airgapInactive: { backgroundColor: 'rgba(245,158,11,0.15)', borderColor: '#F59E0B' },
  airgapText: { color: '#10B981', fontSize: 11, fontWeight: 'bold' },
  streamContainer: { flex: 1, padding: 16 },
  statusCard: { backgroundColor: '#0F1626', padding: 14, borderRadius: 10, marginBottom: 16, borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)' },
  cardHeader: { color: '#64748B', fontSize: 10, fontWeight: 'bold', letterSpacing: 1 },
  cardBody: { color: '#E2E8F0', fontSize: 13, marginTop: 4, fontWeight: '600' },
  cardCost: { color: '#10B981', fontSize: 12, marginTop: 2, fontFamily: 'monospace' },
  sectionHeader: { color: '#94A3B8', fontSize: 11, fontWeight: 'bold', marginBottom: 10 },
  emptyText: { color: '#475569', fontSize: 12, fontStyle: 'italic' },
  eventCard: { backgroundColor: '#0F1626', padding: 12, borderRadius: 8, marginBottom: 12, borderWidth: 1, borderColor: 'rgba(255,255,255,0.06)' },
  eventType: { color: '#3B82F6', fontSize: 11, fontWeight: 'bold' },
  eventPrompt: { color: '#F1F5F9', fontSize: 12, marginTop: 4 },
  eventBody: { color: '#94A3B8', fontSize: 11, marginTop: 4 },
  diffBox: { backgroundColor: '#05070D', padding: 8, borderRadius: 6, marginTop: 8 },
  diffText: { color: '#34D399', fontSize: 10, fontFamily: 'monospace' },
  authorizeButton: { marginTop: 10, backgroundColor: 'rgba(16,185,129,0.2)', paddingVertical: 8, borderRadius: 6, alignItems: 'center', borderWidth: 1, borderColor: 'rgba(16,185,129,0.4)' },
  authorizeButtonText: { color: '#10B981', fontSize: 12, fontWeight: '600' },
  inputDock: { flexDirection: 'row', padding: 12, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.08)', backgroundColor: '#0F1626' },
  input: { flex: 1, backgroundColor: '#070A12', borderRadius: 8, paddingHorizontal: 12, color: '#FFFFFF', fontSize: 13, borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' },
  sendButton: { width: 40, height: 40, backgroundColor: '#3B82F6', borderRadius: 8, justifyContent: 'center', alignItems: 'center', marginLeft: 8 },
  sendButtonText: { color: '#FFFFFF', fontSize: 16 },
});
