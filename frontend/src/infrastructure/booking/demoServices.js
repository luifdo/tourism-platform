import { DEMO_SERVICIOS } from '../catalog/demoCatalogo.js'

/** Servicios de demostración del simulador de reservas: capacidad diaria, tarifa base y particularidades de cada uno. */
export const demoServices = Object.fromEntries(
  DEMO_SERVICIOS.map((s) => [
    s.id,
    {
      fee: s.tarifaBase,
      capacidad: s.capacidadDiaria,
      // La quebrada cierra los lunes; los sábados de Bahía Concha cuestan 20 % más
      ...(s.id === 'quebrada-valencia' ? { cierra: [1] } : {}),
      ...(s.id === 'bahia-concha' ? { recargo: { dia: 6, factor: 1.2 } } : {}),
    },
  ]),
)
