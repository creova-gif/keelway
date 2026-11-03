/**
 * Local confirmation before a phone approves an agent action: Face ID / fingerprint, else the
 * device passcode, else an explicit confirm dialog. The server token is still the real gate.
 */
import { Alert, Platform } from 'react-native';
import * as LocalAuthentication from 'expo-local-authentication';
import * as Haptics from 'expo-haptics';

function confirmDialog(message: string): Promise<boolean> {
  if (Platform.OS === 'web') return Promise.resolve(globalThis.confirm?.(message) ?? false);
  return new Promise((resolve) =>
    Alert.alert('Keelway', message, [
      { text: 'Cancel', style: 'cancel', onPress: () => resolve(false) },
      { text: 'OK', onPress: () => resolve(true) },
    ]),
  );
}

export async function confirmLocally(prompt: string): Promise<boolean> {
  if (Platform.OS === 'web') return confirmDialog(prompt);
  const level = await LocalAuthentication.getEnrolledLevelAsync();
  if (level === LocalAuthentication.SecurityLevel.NONE) return confirmDialog(prompt);
  await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  const result = await LocalAuthentication.authenticateAsync({ promptMessage: prompt, disableDeviceFallback: false });
  await Haptics.notificationAsync(
    result.success ? Haptics.NotificationFeedbackType.Success : Haptics.NotificationFeedbackType.Error,
  );
  return result.success;
}
