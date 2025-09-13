/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import svgr from 'vite-plugin-svgr';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // --- 👇 ВОТ ЭТОТ НОВЫЙ БЛОК ВСЁ ИСПРАВИТ ---
  esbuild: {
    loader: 'jsx',
    include: /src\/.*\.jsx?$/, // Обрабатывать .js и .jsx файлы
    exclude: [],
  },
});