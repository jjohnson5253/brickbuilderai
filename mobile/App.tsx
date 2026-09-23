import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { BrickBuilderWebView } from './src/BrickBuilderWebView';

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <BrickBuilderWebView />
    </SafeAreaProvider>
  );
}
