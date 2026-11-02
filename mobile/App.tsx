import React, { useCallback, useEffect, useState } from 'react';
import { I18nManager, StyleSheet, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as Linking from 'expo-linking';
import PairScreen from './src/screens/PairScreen';
import MissionControlScreen from './src/screens/MissionControlScreen';
import { Connection, parseStudioLink } from './src/services/api';
import { loadConnection, saveConnection } from './src/services/storage';
import { Lang, isRTL } from './src/i18n';
import { color } from './src/theme';

export default function App() {
  const [ready, setReady] = useState(false);
  const [conn, setConn] = useState<Connection | null>(null);
  const [lang, setLangState] = useState<Lang>('en');
  const [pendingLink, setPendingLink] = useState<string | null>(null);

  useEffect(() => {
    loadConnection().then((c) => {
      setConn(c);
      setReady(true);
    });
  }, []);

  // keelway://pair?link=<url-encoded Studio link> only pre-fills the pair screen; the user still
  // sees the host and presses Connect, which verifies it with whoami before replacing anything.
  const url = Linking.useURL();
  useEffect(() => {
    if (!url) return;
    const link = Linking.parse(url).queryParams?.link;
    if (typeof link === 'string' && parseStudioLink(link)) setPendingLink(link);
  }, [url]);

  const setLang = (l: Lang) => {
    I18nManager.allowRTL(isRTL(l));
    setLangState(l);
  };

  const onPaired = useCallback((c: Connection) => {
    saveConnection(c);
    setConn(c);
    setPendingLink(null);
  }, []);

  const onDisconnect = useCallback(() => {
    saveConnection(null);
    setConn(null);
  }, []);

  return (
    <View style={styles.root}>
      <StatusBar style="light" />
      {ready && (conn && !pendingLink
        ? <MissionControlScreen key={`${conn.baseUrl}#${conn.token}`} conn={conn} lang={lang} setLang={setLang} onDisconnect={onDisconnect} />
        : <PairScreen
            key={pendingLink ?? ''}
            lang={lang}
            setLang={setLang}
            onPaired={onPaired}
            initialLink={pendingLink ?? ''}
            onCancel={conn ? () => setPendingLink(null) : undefined}
          />)}
    </View>
  );
}

const styles = StyleSheet.create({ root: { flex: 1, backgroundColor: color.ink } });
