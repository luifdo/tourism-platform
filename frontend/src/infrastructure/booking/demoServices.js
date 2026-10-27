import { capacity, experiences } from '../../data/mock.js'

/** Servicios de demostración del simulador: capacidad diaria, tarifa base y particularidades de cada uno. */
export const demoServices = Object.fromEntries(
  experiences.map((e) => [
    e.id,
    {
      fee: e.fee,
      capacidad: capacity[e.id] ?? 10,
      // La quebrada cierra los lunes; los sábados de Bahía Concha cuestan 20 % más
      ...(e.id === 'quebrada-valencia' ? { cierra: [1] } : {}),
      ...(e.id === 'bahia-concha' ? { recargo: { dia: 6, factor: 1.2 } } : {}),
    },
  ]),
)
