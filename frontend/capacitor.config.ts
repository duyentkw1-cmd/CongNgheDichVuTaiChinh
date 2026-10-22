import type { CapacitorConfig } from '@capacitor/cli';
// Optional native shell. See README before packaging. Web demo works without Android Studio.
const config: CapacitorConfig = {
  appId: 'vn.sothuchi.demo', appName: 'Sổ Thu Chi AI', webDir: 'dist',
  ...(process.env.NATIVE_DEMO_URL ? {server:{url:process.env.NATIVE_DEMO_URL,cleartext:process.env.NATIVE_DEMO_URL.startsWith('http:')}} : {})
};
export default config;
