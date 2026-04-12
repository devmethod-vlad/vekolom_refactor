import { defineConfig } from 'vite';
import { fileURLToPath, URL } from 'node:url';
import path from 'node:path';

const frontendRoot = fileURLToPath(new URL('.', import.meta.url));
const projectRoot = path.resolve(frontendRoot, '..');

/**
 * Возвращает абсолютный путь до каталога сборки modern-ассетов.
 *
 * Почему не хардкодим '../static/dist'
 * -----------------------------------
 * Путь до production-ассетов уже задаётся в backend-настройках через
 * VITE_BUILD_DIR. Если в vite.config.js оставить жёсткую строку, рано или
 * поздно кто-то поменяет .env и получит рассинхрон двух миров.
 */
function resolveBuildDir(buildDir) {
  if (!buildDir) {
    return path.resolve(projectRoot, 'static/dist');
  }

  return path.isAbsolute(buildDir)
    ? buildDir
    : path.resolve(projectRoot, buildDir);
}

const viteBuildDir = resolveBuildDir(process.env.VITE_BUILD_DIR);
const viteDevServerOrigin = process.env.VITE_DEV_SERVER_ORIGIN || 'http://127.0.0.1:5173';

/**
 * Vite отвечает только за modern JS/CSS.
 *
 * Legacy-скрипты принципиально не проходят через Vite:
 * они живут внутри STATIC_ROOT и подключаются шаблонами как обычные
 * classic <script>. Это важно для jQuery и старых плагинов, которые
 * завязаны на строгий синхронный порядок выполнения.
 */
export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    origin: viteDevServerOrigin,
    cors: true,
    watch: {
      // На Docker Desktop / Windows polling обычно надёжнее обычных fs events.
      usePolling: process.env.CHOKIDAR_USEPOLLING === 'true',
    },
    hmr: {
      host: process.env.FRONTEND_HMR_HOST || 'localhost',
      protocol: process.env.FRONTEND_HMR_PROTOCOL || 'ws',
      port: Number(process.env.FRONTEND_HMR_PORT || '5173'),
    },
  },

  build: {
    outDir: viteBuildDir,
    emptyOutDir: true,
    manifest: 'manifest.json',
    sourcemap: false,
    rollupOptions: {
      input: {
        base: fileURLToPath(new URL('./src/js/entries/base.js', import.meta.url)),
        // home: fileURLToPath(new URL('./src/js/entries/home.js', import.meta.url)),
        // contacts: fileURLToPath(new URL('./src/js/entries/contacts.js', import.meta.url)),
        // pricelist: fileURLToPath(new URL('./src/js/entries/pricelist.js', import.meta.url)),
      },
    },
  },
});
