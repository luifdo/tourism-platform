import { defineConfig } from 'vitest/config'

// Las pruebas cubren las capas sin Vue (dominio, aplicación, infraestructura): corren en Node, sin plugins
export default defineConfig({
  test: { include: ['tests/**/*.test.js'], environment: 'node' },
})
