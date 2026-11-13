# Material de origen (no se sirve)

`hero.mp4` es el video de la portada (1280×720, 24 fps, 10 s). La portada **no lo reproduce**: usa los fotogramas de `public/hero/`
(`d/` = 1280×720 para pantallas anchas, `m/` = 406×720, el centro del cuadro, para teléfonos en vertical; 120 cuadros WebP cada uno, uno de cada
dos del video). Ver `src/lib/heroFrames.js` y `src/components/HeroScroll.vue`.

Para regenerarlos: dibujar el video en un canvas cuadro a cuadro (`currentTime = i * 2 / 24`) y guardar cada uno con
`canvas.toBlob(..., 'image/webp', 0.55)` (el conjunto `m` recorta `sx = (1280 - 406) / 2`), o con ffmpeg:
`ffmpeg -i hero.mp4 -vf "select='not(mod(n,2))',scale=1280:720" -c:v libwebp -quality 55 public/hero/d/f%03d.webp`
(y `crop=406:720` antes de `scale` para el conjunto `m`; ffmpeg numera desde 001).
