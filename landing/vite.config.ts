import { realpathSync } from 'node:fs'
import { defineConfig, searchForWorkspaceRoot } from 'vite'
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
    fs: {
      // Dans un worktree, node_modules est un lien vers celui du dépôt principal :
      // les polices @fontsource sortent alors du périmètre servi par Vite (403) et
      // la page retombe sur les polices de repli.
      allow: [searchForWorkspaceRoot(process.cwd()), realpathSync('node_modules')],
    },
  },
})
