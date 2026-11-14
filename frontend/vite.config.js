import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// En GitHub Pages el sitio vive en /<repo>/; el workflow define VITE_BASE=/tourism-platform/
const base = process.env.VITE_BASE || '/'

export default defineConfig({
  base,
  plugins: [
    vue(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Samaland adventure · Turismo regenerativo en Santa Marta',
        short_name: 'Samaland',
        description: 'Catálogo, mapa de capacidad de carga y reservas sin comisiones en Santa Marta.',
        lang: 'es',
        theme_color: '#021F39',
        background_color: '#FAF6ED',
        display: 'standalone',
        id: base,
        start_url: base,
        scope: base,
        orientation: 'any',
        categories: ['travel', 'lifestyle'],
        display_override: ['standalone', 'minimal-ui'],
        icons: [
          { src: `${base}icons/icon-192.png`, sizes: '192x192', type: 'image/png' },
          { src: `${base}icons/icon-512.png`, sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: `${base}icons/maskable-512.png`, sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
        shortcuts: [
          { name: 'Mis reservas', short_name: 'Reservas', url: `${base}mis-reservas`, icons: [{ src: `${base}icons/icon-192.png`, sizes: '192x192', type: 'image/png' }] },
          { name: 'Explorar experiencias', short_name: 'Explorar', url: `${base}#catalogo`, icons: [{ src: `${base}icons/icon-192.png`, sizes: '192x192', type: 'image/png' }] },
        ],
      },
      workbox: {
        // La aplicación se sirve "cache first"; el video del hero (5 MB) no se guarda sin conexión
        globPatterns: ['**/*.{js,css,html,png,jpg,svg,webmanifest,woff2}'], // woff2: las fuentes van con la app (autoalojadas)
        globIgnores: ['**/*.mp4'],
        navigateFallback: `${base}index.html`,
        navigateFallbackDenylist: [/\/api\//],
        runtimeCaching: [
          {
            // Catálogo PÚBLICO: stale-while-revalidate (RNF-13). Solo las rutas públicas del gateway y solo peticiones SIN sesión: lo
            // que lleva Authorization es de una persona (métricas, servicios del prestador, analítica de la Entidad...) y esta caché
            // la sirve a cualquiera, antes de revisar nada, y sobrevive al cierre de sesión. Nombre nuevo (-v2): la caché «catalogo»
            // de versiones anteriores traía rutas privadas y se borra al arrancar (lib/limpiezaLocal.js).
            urlPattern: ({ url, request }) =>
              request.method === 'GET' && !request.headers.has('Authorization')
              && /^\/api\/catalog\/(servicios(\/[^/]+)?|buscar|zonas|alertas|mapa\/[^/]+)$/.test(url.pathname),
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'catalogo-publico-v2', expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 * 7 } },
          },
          {
            // Mapa: solo las teselas ya vistas (política de uso de OpenStreetMap), nunca descarga masiva
            urlPattern: ({ url }) => url.hostname.endsWith('tile.openstreetmap.org'),
            handler: 'CacheFirst',
            options: { cacheName: 'teselas-osm', expiration: { maxEntries: 150, maxAgeSeconds: 60 * 60 * 24 * 14 }, cacheableResponse: { statuses: [0, 200] } },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    // El frontend solo habla con el Gateway (Traefik); en desarrollo se redirige /api
    proxy: { '/api': { target: 'http://localhost:80', changeOrigin: true } },
  },
})
