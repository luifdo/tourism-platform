// ESC-01 (Plan §8.4): una falla en el Módulo de Reseñas no interrumpe la navegación en el
// catálogo. Corre a la vez:
//   * catalog: búsqueda a tasa constante. Es el criterio: 0 errores y p95 < 2 s.
//   * review: el resumen público de un servicio. Solo se mide (sin umbral): con 1 réplica,
//     review no responde mientras se reinicia, y el Plan lo acepta.
// Mientras corre, scripts/esc01_aislamiento.py tumba la API de review tres veces.
//
//   PERFIL=completo CATALOG_URL=https://... REVIEW_URL=https://... SERVICIO_ID=... k6 run esc01.js
//
// Cómo correrlo en el Kubernetes local o en k3s: k6/README.md.
import http from 'k6/http';
import { check } from 'k6';
import { Rate } from 'k6/metrics';

const CATALOG = __ENV.CATALOG_URL || 'http://catalog-service.turismo-app:8002/api/catalog';
const REVIEW = __ENV.REVIEW_URL || 'http://review-service.turismo-app:8004/api/reviews';
const SERVICIO = __ENV.SERVICIO_ID || '00000000-0000-0000-0000-000000000000';
const PERFILES = {
  humo: { catalog: 20, review: 5, duration: '4m' },
  completo: { catalog: 200, review: 20, duration: '10m' },
};
const perfil = PERFILES[__ENV.PERFIL || 'humo'];

const catalogOk = new Rate('catalog_disponible');
const reviewOk = new Rate('review_disponible');

export const options = {
  scenarios: {
    catalog: {
      executor: 'constant-arrival-rate',
      exec: 'catalogo',
      rate: perfil.catalog,
      timeUnit: '1s',
      duration: perfil.duration,
      preAllocatedVUs: 20,
      maxVUs: 200,
    },
    review: {
      executor: 'constant-arrival-rate',
      exec: 'resenas',
      rate: perfil.review,
      timeUnit: '1s',
      duration: perfil.duration,
      preAllocatedVUs: 5,
      maxVUs: 50,
    },
  },
  thresholds: {
    // El criterio de ESC-01: el catálogo no siente la caída de review.
    catalog_disponible: ['rate==1'],
    'http_req_duration{modulo:catalog}': ['p(95)<2000'],
    // review no tiene umbral: su disponibilidad se reporta (con 1 réplica cae al reiniciarse).
    review_disponible: ['rate>=0'],
    'dropped_iterations{scenario:catalog}': ['count==0'],
  },
};

// Puntos dentro de las zonas iniciales (centro histórico, El Rodadero, Taganga, Minca...).
const PUNTOS = [
  [11.2408, -74.2110], [11.2045, -74.2290], [11.2680, -74.1900],
  [11.1426, -74.1178], [11.3000, -74.1500], [11.3090, -74.0750],
];

export function catalogo() {
  const [lat, lon] = PUNTOS[Math.floor(Math.random() * PUNTOS.length)];
  const r = http.get(`${CATALOG}/buscar?lat=${lat}&lon=${lon}&radio_m=5000`, {
    tags: { modulo: 'catalog' },
    timeout: '10s',
  });
  catalogOk.add(r.status === 200);
  check(r, { 'catalog responde 200': (res) => res.status === 200 });
}

export function resenas() {
  const r = http.get(`${REVIEW}/servicios/${SERVICIO}/resumen`, {
    tags: { modulo: 'review' },
    timeout: '5s',
  });
  reviewOk.add(r.status === 200);
}
