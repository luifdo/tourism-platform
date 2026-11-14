/*
 * Secuencia de fotogramas de la portada (public/hero/{d,m}/f001..f120.webp), sacada del video hero.mp4 (24 fps, 10 s; un cuadro de
 * cada dos). Se dibuja en un canvas según el scroll, en lugar de mover el `currentTime` de un <video>: un video exige permiso para
 * reproducirse (iOS lo niega en modo de bajo consumo y sin gesto) y no se mueve; una imagen se carga siempre.
 *   d: 1280×720, para pantallas anchas y tabletas.   m: 406×720 (el centro del cuadro, formato vertical), para teléfonos.
 */
export const TOTAL = 120

export const rutaDeCuadro = (base, conjunto, i) => `${base}hero/${conjunto}/f${String(i + 1).padStart(3, '0')}.webp`

/** Conjunto según la ventana: el vertical y liviano para teléfonos en vertical; el ancho para todo lo demás. */
export const conjuntoPara = (ancho, alto) => (ancho < 768 && alto > ancho ? 'm' : 'd')

/** Cuadro que corresponde a un avance de 0 a 1 del scroll. */
export const indiceDeAvance = (avance, total = TOTAL) => Math.min(total - 1, Math.max(0, Math.round((Number(avance) || 0) * (total - 1))))

/**
 * Orden en que se piden los cuadros: primero el inicio y el final, luego de a 16, de a 8, de a 4, de a 2 y el resto. Así, aunque la
 * conexión sea lenta, el scroll ya mueve la imagen con pocos saltos grandes y se va afinando. `paso` > 1 (ahorro de datos) se queda
 * solo con los cuadros múltiplos de `paso` (más el último).
 */
export function ordenDeCarga(total = TOTAL, paso = 1) {
  const visto = new Set()
  const orden = []
  const agregar = (i) => { if (i >= 0 && i < total && !visto.has(i)) { visto.add(i); orden.push(i) } }
  agregar(0); agregar(total - 1)
  for (const salto of [16, 8, 4, 2, 1]) for (let i = 0; i < total; i += salto) agregar(i)
  return paso > 1 ? orden.filter((i) => i % paso === 0 || i === total - 1) : orden
}

/** El cuadro ya cargado más cercano a `i` (null si no hay ninguno). `cargado[i]` es verdadero cuando ese cuadro está listo. */
export function cuadroMasCercano(i, cargado) {
  if (cargado[i]) return i
  for (let d = 1; d < cargado.length; d++) {
    if (i - d >= 0 && cargado[i - d]) return i - d
    if (i + d < cargado.length && cargado[i + d]) return i + d
  }
  return null
}

/** Rectángulo de origen para dibujar una imagen (ancho × alto) cubriendo un lienzo (como `object-fit: cover`, centrado). */
export function recorteCover(anchoImg, altoImg, anchoLienzo, altoLienzo) {
  const escala = Math.max(anchoLienzo / anchoImg, altoLienzo / altoImg)
  const w = anchoLienzo / escala
  const h = altoLienzo / escala
  return { sx: (anchoImg - w) / 2, sy: (altoImg - h) / 2, sw: w, sh: h }
}
