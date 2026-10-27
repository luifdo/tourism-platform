// ESC-02 (Plan §8.4): búsqueda del catálogo en temporada alta.
// Perfil completo: 500 solicitudes por segundo durante 10 minutos; p95 < 2 s y 0 errores 5xx.
// Perfil "humo" (por defecto en local): 30 rps durante 1 minuto, para comprobar que todo funciona.
//
//   PERFIL=completo BASE_URL=https://... k6 run buscar.js
//
// Cómo correrlo en el Kubernetes local o en k3s: k6/README.md.
import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://catalog-service.turismo-app:8002/api/catalog';
const PERFILES = {
  humo: { rate: 30, duration: '1m', preAllocatedVUs: 20, maxVUs: 60 },
  completo: { rate: 500, duration: '10m', preAllocatedVUs: 200, maxVUs: 1000 },
};
const perfil = PERFILES[__ENV.PERFIL || 'humo'];

const errores5xx = new Counter('errores_5xx');

export const options = {
  scenarios: {
    buscar: { executor: 'constant-arrival-rate', timeUnit: '1s', ...perfil },
  },
  thresholds: {
    'http_req_duration{escenario:buscar}': ['p(95)<2000'],
    errores_5xx: ['count==0'],
    // Si k6 no logra mandar las peticiones a tiempo, el resultado no vale: hacen falta más VUs.
    dropped_iterations: ['count==0'],
  },
};

// Puntos dentro de las zonas iniciales (centro histórico, El Rodadero, Taganga, Minca...).
const PUNTOS = [
  [11.2408, -74.2110], [11.2045, -74.2290], [11.2680, -74.1900],
  [11.1426, -74.1178], [11.3000, -74.1500], [11.3090, -74.0750],
];
const CATEGORIAS = ['', 'PLAYA', 'CULTURA', 'NATURALEZA', 'GASTRONOMIA'];
const ORDEN = ['', 'distancia', 'calificacion', 'precio'];

function alAzar(lista) {
  return lista[Math.floor(Math.random() * lista.length)];
}

export default function () {
  const [lat, lon] = alAzar(PUNTOS);
  const params = [`lat=${lat}`, `lon=${lon}`, `radio_m=${alAzar([2000, 5000, 10000])}`];
  const categoria = alAzar(CATEGORIAS);
  const orden = alAzar(ORDEN);
  if (categoria) params.push(`categoria=${categoria}`);
  if (orden) params.push(`orden=${orden}`);
  if (Math.random() < 0.3) params.push(`pagina=${1 + Math.floor(Math.random() * 3)}`);

  const r = http.get(`${BASE}/buscar?${params.join('&')}`, {
    headers: { 'Accept-Language': Math.random() < 0.8 ? 'es' : 'en' },
    tags: { escenario: 'buscar' },
  });
  if (r.status >= 500) errores5xx.add(1);
  check(r, { 'responde 200': (res) => res.status === 200 });
}
