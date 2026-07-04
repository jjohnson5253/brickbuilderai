
  import { defineConfig } from 'vite';
  import react from '@vitejs/plugin-react-swc';
  import tailwindcss from '@tailwindcss/vite';
  import path from 'path';

  const apiRoutes = [
    '/imageToBricks',
    '/textToBricks',
    '/glbToBricks',
    '/ldrToMpd',
    '/partToMpd',
    '/ldrToBrickOwl',
    '/estimatePrice',
    '/getPrice',
    '/resizeModel',
    '/promptEditModel',
    '/llmRender',
    '/createCheckoutSession',
    '/stripeWebhook',
    '/getGeneration',
    '/generation',
    '/getUserGenerations',
    '/getGenerationsByImage',
    '/getCommunityGenerations',
    '/updateModel',
    '/updateLdrAndPartsList',
    '/sendWaitlistEmail',
    '/toggleIsCommunity',
    '/claimGeneration',
    '/updateGenerationName',
    '/updateImagePreview',
    '/updateUsername',
    '/local-storage',
  ];

  export default defineConfig({
    plugins: [react(), tailwindcss()],
    server: {
      port: 3000,
      open: true,
      allowedHosts: ['.ngrok-free.app'],
      proxy: Object.fromEntries(
        apiRoutes.map((route) => [
          route,
          {
            target: 'http://127.0.0.1:8002',
            changeOrigin: true,
          },
        ])
      ),
    },
    resolve: {
      extensions: ['.js', '.jsx', '.ts', '.tsx', '.json'],
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    build: {
      target: 'esnext',
    }
  });
