import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Lang, languages } from '../i18n';
import { color } from '../theme';

export default function LanguagePicker({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  return (
    <View style={styles.row} accessibilityRole="radiogroup">
      {languages.map((l) => (
        <TouchableOpacity
          key={l.code}
          onPress={() => setLang(l.code)}
          style={[styles.chip, l.code === lang && styles.on]}
          accessibilityRole="radio"
          accessibilityState={{ selected: l.code === lang }}
        >
          <Text style={[styles.text, l.code === lang && styles.onText]}>{l.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', justifyContent: 'center', gap: 6, marginBottom: 16 },
  chip: { minWidth: 44, minHeight: 32, paddingHorizontal: 10, borderRadius: 16, borderWidth: 1, borderColor: color.line, alignItems: 'center', justifyContent: 'center' },
  on: { borderColor: color.accent, backgroundColor: 'rgba(201,164,92,0.12)' },
  text: { color: color.muted, fontSize: 12, fontWeight: '600' },
  onText: { color: color.accent },
});
