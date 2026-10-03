#!/usr/bin/env node
// Commande globale `monumia`, posée par un `npm link` à la racine du dépôt.
//
// Le lien pointe sur UN dépôt, mais on veut lancer celui (ou le worktree) où
// l'on se trouve : on résout donc la racine git du dossier courant, et on
// n'utilise la copie du lien qu'en dehors de tout dépôt monumia.

import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const r = spawnSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' })
let cible = r.status === 0 ? path.join(r.stdout.trim(), 'scripts', 'dev', 'monumia.mjs') : null
if (!cible || !fs.existsSync(cible)) {
  cible = path.join(path.dirname(fs.realpathSync(fileURLToPath(import.meta.url))), 'monumia.mjs')
  process.stderr.write(`(hors d'un dépôt monumia : lancement de ${path.resolve(cible, '..', '..', '..')})\n`)
}
await import(pathToFileURL(cible).href)
