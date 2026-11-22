import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AppState, RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { AgentRun, Connection, KeelwayClient, KeelwayError, PendingApproval, StudioStatus, WhoAmI } from '../services/api';
import { confirmLocally } from '../services/biometrics';
import { color, mono } from '../theme';
import { Lang, isRTL, strings } from '../i18n';
import LanguagePicker from './LanguagePicker';

const POLL_MS = 3000;
const MAX_BACKOFF_MS = 30000;

function preview(p: PendingApproval): string {
  const a = p.arguments || {};
  const target = a.path || a.command || '';
  const body = typeof a.content === 'string' ? `\n${a.content.split('\n').slice(0, 8).join('\n')}` : '';
  return `${target}${body}`.trim();
}

export default function MissionControlScreen({ conn, lang, setLang, onDisconnect }: {
  conn: Connection; lang: Lang; setLang: (l: Lang) => void; onDisconnect: () => void;
}) {
  const t = strings[lang];
  const rtl = isRTL(lang);
  const client = useRef(new KeelwayClient(conn)).current;
  const [status, setStatus] = useState<StudioStatus | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [me, setMe] = useState<WhoAmI | null>(null);
  const [online, setOnline] = useState(true);
  const [syncedAt, setSyncedAt] = useState<Date | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const failures = useRef(0);

  const refresh = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([client.status(), client.runs()]);
      if (!me) setMe(await client.whoami());
      setStatus(s);
      setRuns(r);
      setOnline(true);
      setSyncedAt(new Date());
      failures.current = 0;
    } catch (e) {
      if (e instanceof KeelwayError && e.status === 401) return onDisconnect();
      setOnline(false);
      failures.current += 1;
    }
  }, [client, me, onDisconnect]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let active = AppState.currentState === 'active';
    const tick = async () => {
      if (active) await refresh();
      const delay = Math.min(POLL_MS * 2 ** failures.current, MAX_BACKOFF_MS);
      timer = setTimeout(tick, delay);
    };
    tick();
    const sub = AppState.addEventListener('change', (s) => {
      active = s === 'active';
      if (active) refresh();
    });
    return () => {
      clearTimeout(timer);
      sub.remove();
    };
  }, [refresh]);

  const canApprove = !!me?.permissions.includes('approve_agent_steps');
  const canSetAirGap = !!me?.permissions.includes('approve_tier3');

  const decide = async (run: AgentRun, approved: boolean) => {
    if (!run.pending_approval) return;
    if (approved && !(await confirmLocally(`${t.authPrompt}: ${run.pending_approval.tool_name}`))) return;
    setBusy(run.task_id);
    try {
      await client.decide(run.task_id, approved);
      setNotice(`${approved ? t.approved : t.denied}: ${run.pending_approval.tool_name}`);
      await refresh();
    } catch (e) {
      setNotice(e instanceof KeelwayError ? e.message : t.unreachable);
    } finally {
      setBusy(null);
    }
  };

  const toggleAirGap = async () => {
    if (!status || !canSetAirGap) return;
    if (!status.air_gapped || (await confirmLocally(t.hybrid))) {
      try {
        await client.setAirGap(!status.air_gapped);
        await refresh();
      } catch (e) {
        setNotice(e instanceof KeelwayError ? e.message : t.unreachable);
      }
    }
  };

  const waiting = runs.filter((r) => r.pending_approval);
  const align = rtl ? styles.rtl : null;

  const watchStatus = (run: AgentRun, tt: typeof t): { label: string; style: { color: string } } => {
    if (run.pending_approval) return { label: tt.gated, style: { color: color.accent } };
    const st = run.status.toLowerCase();
    if (st === 'done' || st === 'completed' || st === 'sealed' || st === 'success')
      return { label: tt.sealed, style: { color: color.success } };
    if (st === 'denied' || st === 'failed' || st === 'error')
      return { label: run.status, style: { color: color.error } };
    return { label: run.status, style: { color: color.info } };
  };

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={false} onRefresh={refresh} tintColor={color.accent} />}
    >
      <View style={[styles.header, rtl && styles.rowReverse]}>
        <View>
          <Text style={styles.brand}>Keelway</Text>
          <Text style={styles.host}>{conn.baseUrl.replace(/^https?:\/\//, '')}</Text>
        </View>
        {status && (
          <TouchableOpacity
            onPress={toggleAirGap}
            disabled={!canSetAirGap}
            style={[styles.badge, status.air_gapped ? styles.badgeGap : styles.badgeHybrid]}
            accessibilityRole="switch"
            accessibilityState={{ checked: status.air_gapped, disabled: !canSetAirGap }}
            accessibilityHint={t.airGapHint}
            testID="airgap"
          >
            <Text style={[styles.badgeText, { color: status.air_gapped ? color.accent : color.accent }]}>
              {status.air_gapped ? t.airGapped : t.hybrid}
            </Text>
          </TouchableOpacity>
        )}
      </View>

      <View style={[styles.sync, !online && styles.syncOff]} accessibilityLiveRegion="polite">
        <Text style={[styles.syncText, align]}>
          {online ? `${t.synced} ${syncedAt ? syncedAt.toLocaleTimeString() : ''}` : t.offline}
        </Text>
      </View>

      {notice && (
        <TouchableOpacity onPress={() => setNotice(null)} style={styles.notice} accessibilityLiveRegion="polite">
          <Text style={[styles.noticeText, align]}>{notice}</Text>
        </TouchableOpacity>
      )}

      {waiting.map((run) => (
        <View key={run.task_id} style={styles.approval} testID="approval-card">
          <Text style={[styles.gateEyebrow, align]}>{`${t.gate} · ${run.task_id} · NOW`}</Text>
          <Text style={[styles.goal, align]} accessibilityRole="header">{run.goal}</Text>
          <View style={styles.gateDetail} testID="gate-detail">
            <Text style={styles.gateRow}>
              <Text style={styles.gateKey}>{t.action}{'  '}</Text>
              <Text style={styles.gateVal}>
                {run.pending_approval!.tool_name}{run.pending_approval!.is_mutation ? ` · ${t.mutation}` : ''}
              </Text>
            </Text>
            <Text style={styles.gateRow}>
              <Text style={styles.gateKey}>{t.proof}{'  '}</Text>
              <Text style={[styles.gateVal, { color: color.accent }]}>{t.sealedEitherWay}</Text>
            </Text>
          </View>
          {!!preview(run.pending_approval!) && <Text style={styles.code} numberOfLines={10}>{preview(run.pending_approval!)}</Text>}
          {canApprove ? (
            <View style={[styles.actions, rtl && styles.rowReverse]}>
              <TouchableOpacity
                style={[styles.btn, styles.approve]}
                disabled={busy === run.task_id}
                onPress={() => decide(run, true)}
                accessibilityRole="button"
                testID="approve"
              >
                <Text style={styles.approveText}>{t.approve}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.btn, styles.deny]}
                disabled={busy === run.task_id}
                onPress={() => decide(run, false)}
                accessibilityRole="button"
                testID="deny"
              >
                <Text style={styles.denyText}>{t.deny}</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <Text style={[styles.muted, align]}>{t.noPermission}</Text>
          )}
          <Text style={styles.gateFoot}>{t.gateFoot}</Text>
        </View>
      ))}

      <Text style={[styles.section, align]} accessibilityRole="header">{t.runs}</Text>
      {runs.length === 0 && <Text style={[styles.muted, align]}>{t.noRuns}</Text>}
      {runs.map((run) => (
        <View key={run.task_id} style={styles.run}>
          <Text style={[styles.goal, align]} numberOfLines={2}>{run.goal}</Text>
          <View style={[styles.runMeta, rtl && styles.rowReverse]}>
            <Text style={[styles.status, watchStatus(run, t).style]}>{watchStatus(run, t).label}</Text>
            <Text style={styles.muted}>{run.steps_done}/{run.steps_total} {t.steps}</Text>
          </View>
          <View style={styles.bar} accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: run.steps_total || 1, now: run.steps_done }}>
            <View style={[styles.barFill, { width: `${run.steps_total ? (100 * run.steps_done) / run.steps_total : 0}%` }]} />
          </View>
        </View>
      ))}

      {status && (
        <Text style={[styles.footer, align]}>{t.localModel}: {status.local_model} · v{status.version}</Text>
      )}
      <LanguagePicker lang={lang} setLang={setLang} />
      <TouchableOpacity onPress={onDisconnect} style={styles.disconnect} accessibilityRole="button" testID="disconnect">
        <Text style={styles.muted}>{t.disconnect}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.canvas },
  content: { padding: 16, paddingTop: 56, maxWidth: 720, width: '100%', alignSelf: 'center' },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  rowReverse: { flexDirection: 'row-reverse' },
  brand: { color: color.ink, fontSize: 22, fontWeight: '700' },
  host: { color: color.muted, fontFamily: mono, fontSize: 11 },
  badge: { paddingHorizontal: 12, minHeight: 36, justifyContent: 'center', borderRadius: 18, borderWidth: 1 },
  badgeGap: { borderColor: color.accent, backgroundColor: color.accentWash },
  badgeHybrid: { borderColor: color.accent, backgroundColor: color.accentWash },
  badgeText: { fontWeight: '700', fontSize: 12 },
  sync: { paddingVertical: 6, marginBottom: 12 },
  syncOff: { backgroundColor: 'rgba(176,86,78,0.12)', borderRadius: 8, paddingHorizontal: 10 },
  syncText: { color: color.muted, fontSize: 12 },
  notice: { backgroundColor: color.raised, borderRadius: 10, padding: 12, marginBottom: 12 },
  noticeText: { color: color.ink, fontSize: 13 },
  approval: { borderColor: color.accent, borderWidth: 1, borderRadius: 14, padding: 14, marginBottom: 14, backgroundColor: 'rgba(201,164,92,0.06)' },
  gateEyebrow: { color: color.accent, fontFamily: mono, fontSize: 11, letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 6 },
  gateDetail: { backgroundColor: color.surface, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, marginBottom: 12 },
  gateRow: { fontFamily: mono, fontSize: 12, lineHeight: 20 },
  gateKey: { color: color.dim },
  gateVal: { color: color.ink },
  gateFoot: { color: color.dim, fontFamily: mono, fontSize: 10, letterSpacing: 0.8, textTransform: 'uppercase', textAlign: 'center', marginTop: 12 },
  goal: { color: color.ink, fontSize: 15, fontWeight: '600', marginBottom: 4 },
  tool: { color: color.muted, fontFamily: mono, fontSize: 12, marginBottom: 8 },
  code: { color: color.ink, fontFamily: mono, fontSize: 12, backgroundColor: color.canvas, borderRadius: 8, padding: 10, marginBottom: 12 },
  actions: { flexDirection: 'row', gap: 10 },
  btn: { flex: 1, minHeight: 48, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  approve: { backgroundColor: color.accent },
  approveText: { color: color.accentInk, fontWeight: '700' },
  deny: { borderWidth: 1, borderColor: color.line },
  denyText: { color: color.ink, fontWeight: '600' },
  section: { color: color.muted, fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5, marginTop: 8, marginBottom: 8 },
  run: { backgroundColor: color.surface, borderRadius: 12, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: color.line },
  runMeta: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  status: { color: color.accent, fontFamily: mono, fontSize: 12 },
  bar: { height: 4, borderRadius: 2, backgroundColor: color.raised, overflow: 'hidden' },
  barFill: { height: 4, backgroundColor: color.accent },
  muted: { color: color.muted, fontSize: 13 },
  footer: { color: color.muted, fontSize: 12, marginTop: 16, marginBottom: 12 },
  disconnect: { alignItems: 'center', paddingVertical: 14, minHeight: 48 },
  rtl: { textAlign: 'right', writingDirection: 'rtl' },
});
