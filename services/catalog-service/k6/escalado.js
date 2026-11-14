// ESC-08 (Plan §8.4): duplicar la capacidad añadiendo réplicas solo del servicio presionado.
// Perfil completo: rampa hasta 1000 solicitudes por segundo y 30 minutos en total, mezclando
// lo que hace un turista en la PWA (buscar, abrir una ficha, mover el mapa). Mientras corre,
// se registran las réplicas que crea el HPA y cuánto tardan en quedar listas (k6/README.md).
// Perfil "humo" (por defecto en local): rampa corta hasta 60 rps en 3 minutos.
//
//   PERFIL=completo BASE_URL=https://... k6 run escalado.js
//
// La parte de reservas de ESC-08 es de booking-service (su propio script).
import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://catalog-service.turismo-app:8002/api/catalog';
const PERFILES = {
  humo: {
    preAllocatedVUs: 30,
    maxVUs: 120,
    stages: [
      { target: 20, duration: '30s' },
      { target: 60, duration: '1m' },
      { target: 60, duration: '1m' },
      { target: 0, duration: '30s' },
    ],
  },
  completo: {
    preAllocatedVUs: 300,
    maxVUs: 2000,
    stages: [
      { target: 500, duration: '5m' }, // la carga normal de ESC-02
      { target: 1000, duration: '5m' }, // se duplica: el HPA debe responder
      { target: 1000, duration: '15m' }, // se sostiene con las réplicas nuevas
      { target: 0, duration: '5m' }, // baja: el HPA reduce réplicas pasados 5 min
    ],
  },
};
const perfil = PERFILES[__ENV.PERFIL || 'humo'];

const errores5xx = new Counter('errores_5xx');

export const options = {
  scenarios: {
    turista: { executor: 'ramping-arrival-rate', startRate: 5, timeUnit: '1s', ...perfil },
  },
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    errores_5xx: ['count==0'],
  },
};

const PUNTOS = [
  [11.2408, -74.2110], [11.2045, -74.2290], [11.2680, -74.1900],
  [11.1426, -74.1178], [11.3000, -74.1500], [11.3090, -74.0750],
];

function alAzar(lista) {
  return lista[Math.floor(Math.random() * lista.length)];
}

function registrar(r, nombre) {
  if (r.status >= 500) errores5xx.add(1);
  check(r, { [`${nombre} responde 200`]: (res) => res.status === 200 });
}

// Ids de servicios para abrir fichas: se toman de una búsqueda al empezar.
export function setup() {
  const r = http.get(`${BASE}/buscar?tamano=50`);
  const items = r.status === 200 ? r.json('items') : [];
  return { ids: items.map((s) => s.id) };
}

export default function (datos) {
  const [lat, lon] = alAzar(PUNTOS);
  const tirada = Math.random();
  if (tirada < 0.5 || datos.ids.length === 0) {
    const r = http.get(`${BASE}/buscar?lat=${lat}&lon=${lon}&radio_m=5000`, {
      tags: { ruta: 'buscar' },
    });
    registrar(r, 'buscar');
  } else if (tirada < 0.8) {
    const r = http.get(`${BASE}/servicios/${alAzar(datos.ids)}`, {
      tags: { ruta: 'detalle' },
    });
    registrar(r, 'detalle');
  } else {
    const d = 0.05;
    const bbox = [lon - d, lat - d, lon + d, lat + d].map((v) => v.toFixed(4)).join(',');
    const r = http.get(`${BASE}/mapa/servicios?bbox=${bbox}&zoom=${alAzar([11, 13, 15])}`, {
      tags: { ruta: 'mapa' },
    });
    registrar(r, 'mapa');
  }
}
