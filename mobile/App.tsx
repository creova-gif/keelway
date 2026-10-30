import React, { useEffect, useState } from 'react';
import { StyleSheet, View, StatusBar } from 'react-native';
import { StatusBar as ExpoStatusBar } from 'expo-status-bar';
import MissionControlScreen from './src/screens/MissionControlScreen';
import { BiometricGate } from './src/services/biometrics';

export default function App() {
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    async function prepare() {
      // Check biometric hardware on app boot
      await BiometricGate.isSupported();
      setIsReady(true);
    }
    prepare();
  }, []);

  if (!isReady) {
    return <View style={styles.loadingContainer} />;
  }

  return (
    <View style={styles.root}>
      <ExpoStatusBar style="light" />
      <MissionControlScreen />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#05070D',
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#05070D',
  },
});
