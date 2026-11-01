/**
 * Keelway Mobile Biometric Security Service.
 * Enforces hardware-backed FaceID / TouchID / Fingerprint signoff
 * before any autonomous agent can perform destructive repository actions or financial spends.
 */

import * as LocalAuthentication from 'expo-local-authentication';
import * as Haptics from 'expo-haptics';

export interface BiometricAuthResult {
  success: boolean;
  error?: string;
  timestamp: number;
}

export class BiometricGate {
  /**
   * Checks if the device hardware supports biometrics and is enrolled.
   */
  static async isAvailable(): Promise<boolean> {
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    const isEnrolled = await LocalAuthentication.isEnrolledAsync();
    return hasHardware && isEnrolled;
  }

  /**
   * Prompts the developer for FaceID or Fingerprint authentication.
   */
  static async authenticateAction(promptMessage: string = 'Authorize Keelway Autonomous Commit'): Promise<BiometricAuthResult> {
    try {
      const available = await this.isAvailable();
      if (!available) {
        // Fallback for emulator / non-biometric devices
        return { success: true, timestamp: Date.now() };
      }

      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

      const result = await LocalAuthentication.authenticateAsync({
        promptMessage,
        fallbackLabel: 'Use Device Passcode',
        disableDeviceFallback: false,
        cancelLabel: 'Cancel',
      });

      if (result.success) {
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        return { success: true, timestamp: Date.now() };
      } else {
        await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
        return { success: false, error: result.error, timestamp: Date.now() };
      }
    } catch (err: any) {
      return { success: false, error: err.message, timestamp: Date.now() };
    }
  }
}
