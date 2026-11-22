import React, { useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { Connection, KeelwayClient, KeelwayError, pairWithCode, parseStudioLink } from '../services/api';
import { color, mono } from '../theme';
import { Lang, isRTL, strings } from '../i18n';
import LanguagePicker from './LanguagePicker';

export default function PairScreen({ lang, setLang, onPaired, initialLink = '', onCancel }: {
  lang: Lang;
  setLang: (l: Lang) => void;
  onPaired: (c: Connection) => void;
  initialLink?: string;
  onCancel?: () => void;
}) {
  const t = strings[lang];
  const rtl = isRTL(lang);
  const [link, setLink] = useState(initialLink);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const connect = async () => {
    const parsed = parseStudioLink(link);
    if (!parsed) return setError(t.badLink);
    setBusy(true);
    setError(null);
    let pairing = !!parsed.pairCode;
    try {
      const token = parsed.pairCode ? await pairWithCode(parsed.baseUrl, parsed.pairCode, `${Platform.OS} phone`) : parsed.token;
      pairing = false;
      const conn: Connection = { baseUrl: parsed.baseUrl, token };
      await new KeelwayClient(conn).whoami();
      onPaired(conn);
    } catch (e) {
      const rejected = e instanceof KeelwayError && e.status === 401;
      setError(rejected ? (pairing ? t.badPairCode : t.badToken) : t.unreachable);
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <LanguagePicker lang={lang} setLang={setLang} />
      <View style={styles.mark} accessibilityElementsHidden>
        <View style={styles.hull} />
        <View style={styles.keel} />
      </View>
      <Text style={styles.brand}>Keelway</Text>
      <Text style={styles.by}>by Sorvex Labs</Text>
      <Text style={[styles.title, rtl && styles.rtl]} accessibilityRole="header">{t.pairTitle}</Text>
      <Text style={[styles.help, rtl && styles.rtl]}>{t.pairHelp}</Text>
      <Text style={[styles.label, rtl && styles.rtl]} nativeID="link-label">{t.link}</Text>
      <TextInput
        style={styles.input}
        value={link}
        onChangeText={setLink}
        placeholder="http://192.168.1.20:7420/?pair=…"
        placeholderTextColor={color.muted}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        accessibilityLabelledBy="link-label"
        accessibilityLabel={t.link}
        onSubmitEditing={connect}
        testID="pair-link"
      />
      {error && <Text style={[styles.error, rtl && styles.rtl]} accessibilityLiveRegion="polite">{error}</Text>}
      <TouchableOpacity style={[styles.button, busy && styles.dim]} onPress={connect} disabled={busy} accessibilityRole="button" testID="pair-connect">
        {busy ? <ActivityIndicator color={color.accentInk} /> : <Text style={styles.buttonText}>{t.connect}</Text>}
      </TouchableOpacity>
      {onCancel && (
        <TouchableOpacity style={styles.cancel} onPress={onCancel} accessibilityRole="button" testID="pair-cancel">
          <Text style={styles.cancelText}>{t.cancel}</Text>
        </TouchableOpacity>
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: color.canvas, padding: 24, justifyContent: 'center', maxWidth: 520, width: '100%', alignSelf: 'center' },
  mark: { alignItems: 'center', marginBottom: 12 },
  hull: { width: 56, height: 6, borderRadius: 3, backgroundColor: color.accent },
  keel: { width: 6, height: 22, backgroundColor: color.accent, borderBottomLeftRadius: 3, borderBottomRightRadius: 3 },
  brand: { color: color.ink, fontSize: 28, fontWeight: '700', textAlign: 'center' },
  by: { color: color.muted, fontSize: 12, textAlign: 'center', marginBottom: 28 },
  title: { color: color.ink, fontSize: 18, fontWeight: '600', marginBottom: 8 },
  help: { color: color.muted, fontSize: 13, lineHeight: 19, marginBottom: 20 },
  label: { color: color.muted, fontSize: 12, marginBottom: 6 },
  input: { backgroundColor: color.surface, color: color.ink, borderColor: color.line, borderWidth: 1, borderRadius: 10, padding: 14, fontFamily: mono, fontSize: 13 },
  error: { color: color.error, fontSize: 13, marginTop: 10 },
  button: { backgroundColor: color.accent, borderRadius: 10, paddingVertical: 14, alignItems: 'center', marginTop: 16, minHeight: 48, justifyContent: 'center' },
  buttonText: { color: color.accentInk, fontWeight: '700', fontSize: 15 },
  dim: { opacity: 0.6 },
  cancel: { alignItems: 'center', paddingVertical: 14, minHeight: 48, justifyContent: 'center' },
  cancelText: { color: color.muted, fontSize: 14 },
  rtl: { textAlign: 'right', writingDirection: 'rtl' },
});
