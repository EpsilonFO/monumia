import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  // Servie à la racine en prod (monumia.fr) ; sous /landing/ en beta
  // (beta.monumia.fr/landing) via VITE_BASE passé au build Docker.
  base: process.env.VITE_BASE || '/',
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 3001,
  },
})
