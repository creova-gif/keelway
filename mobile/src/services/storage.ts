/** Keeps the connection (incl. token) in the OS keychain; falls back to localStorage on web. */
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import type { Connection } from './api';

const KEY = 'keelway.connection';

export async function loadConnection(): Promise<Connection | null> {
  const raw = Platform.OS === 'web' ? globalThis.localStorage?.getItem(KEY) : await SecureStore.getItemAsync(KEY);
  try {
    return raw ? (JSON.parse(raw) as Connection) : null;
  } catch {
    return null;
  }
}

export async function saveConnection(conn: Connection | null): Promise<void> {
  if (Platform.OS === 'web') {
    if (conn) globalThis.localStorage?.setItem(KEY, JSON.stringify(conn));
    else globalThis.localStorage?.removeItem(KEY);
    return;
  }
  if (conn) await SecureStore.setItemAsync(KEY, JSON.stringify(conn));
  else await SecureStore.deleteItemAsync(KEY);
}
