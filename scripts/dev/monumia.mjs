#!/usr/bin/env node
// Lanceur de dev : prépare le dépôt (ou le worktree) courant, puis ouvre un
// écran plein terminal qui fait tourner backend, frontend et landing.
//
//   npm run monumia                 depuis la racine du dépôt ou d'un worktree
//   monumia                         partout, après un `npm link` à la racine
//
// Aucune dépendance : il doit tourner dans un worktree neuf, avant que quoi
// que ce soit n'y soit installé.

import { spawnSync } from 'node:child_process'
import path from 'node:path'
import readline from 'node:readline'
import { fileURLToPath } from 'node:url'
import { Ecran, restaurerTerminal } from './ecran.mjs'
import { Preparation } from './preparation.mjs'
import { definirServices } from './services.mjs'

const AIDE = `Usage : npm run monumia -- [options]      (ou : monumia [options])

Prépare le dépôt (git fetch, Supabase local, .env, migrations locales,
uv sync, node_modules, ports) puis lance backend, frontend et landing dans un
écran plein terminal.

Options :
  --sans-prep            lance directement les serveurs, sans préparation
  --sans-db              prépare tout sauf les migrations (supabase db push --local)
  --seulement a,b        ne lance au départ que ces serveurs (backend, frontend, landing) ;
                         les autres restent dans la liste, arrêtés (r pour les lancer)
  --prep                 préparation seule, sans lancer les serveurs
  -h, --aide             cette aide
`

function lireOptions(argv) {
  const o = { sansPrep: false, sansDb: false, prepSeule: false, seulement: null }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '-h' || a === '--aide' || a === '--help') {
      process.stdout.write(AIDE)
      process.exit(0)
    } else if (a === '--sans-prep') o.sansPrep = true
    else if (a === '--sans-db') o.sansDb = true
    else if (a === '--prep') o.prepSeule = true
    else if (a === '--seulement') o.seulement = (argv[++i] ?? '').split(',').filter(Boolean)
    else if (a.startsWith('--seulement=')) o.seulement = a.slice('--seulement='.length).split(',').filter(Boolean)
    else {
      process.stderr.write(`Option inconnue : ${a}\n\n${AIDE}`)
      process.exit(2)
    }
  }
  return o
}

function git(cwd, ...args) {
  const r = spawnSync('git', args, { cwd, encoding: 'utf8' })
  return r.status === 0 ? r.stdout.trim() : ''
}

function demander(question) {
  return new Promise((resoudre) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout })
    rl.question(question, (reponse) => {
      rl.close()
      resoudre(/^(o|oui|y|yes)$/i.test(reponse.trim()))
    })
  })
}

const options = lireOptions(process.argv.slice(2))
const racine = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
// Le .git partagé vit dans le dépôt principal : son parent EST le dépôt principal.
const principal = path.dirname(git(racine, 'rev-parse', '--path-format=absolute', '--git-common-dir') || path.join(racine, '.git'))
const branche = git(racine, 'rev-parse', '--abbrev-ref', 'HEAD') || '?'

const services = definirServices(racine)
if (options.seulement) {
  const inconnus = options.seulement.filter((n) => !services.some((s) => s.nom === n))
  if (inconnus.length) {
    process.stderr.write(`Serveur(s) inconnu(s) : ${inconnus.join(', ')} (connus : ${services.map((s) => s.nom).join(', ')})\n`)
    process.exit(2)
  }
}

const preparation = new Preparation({
  racine,
  principal,
  options,
  ports: services.map((s) => ({ port: s.port, nom: s.nom })),
})

const interactif = Boolean(process.stdin.isTTY && process.stdout.isTTY)

if (options.sansPrep) {
  preparation.journal.ajouter('\x1b[2mpréparation ignorée (--sans-prep) : r pour la lancer\x1b[0m')
  preparation.etat = 'pret'
} else {
  preparation.echo = true
  process.stdout.write(`\x1b[1mmonumia\x1b[0m · préparation de ${racine}\n\n`)
  const { echecs } = await preparation.executer({ demander: interactif ? demander : null })
  preparation.echo = false
  if (echecs > 0 && !options.prepSeule) {
    if (!interactif || !(await demander('\nLancer les serveurs quand même ? [o/N] '))) process.exit(1)
  }
  if (options.prepSeule) process.exit(echecs > 0 ? 1 : 0)
}

if (!interactif) {
  process.stderr.write("L'écran des serveurs demande un terminal interactif (ou --prep pour la seule préparation).\n")
  process.exit(1)
}

const entete =
  racine === principal ? `dépôt principal · ${branche}` : `worktree ${path.basename(racine)} · ${branche}`
const ecran = new Ecran({ preparation, services, entete })

// Filets de sécurité : ne jamais laisser le terminal en mode brut, ni des
// serveurs orphelins accrochés à leurs ports.
process.on('exit', () => {
  for (const s of services) s.tuer()
  restaurerTerminal()
})
process.on('SIGTERM', () => ecran.quitter())
process.on('SIGHUP', () => process.exit(0))
process.on('uncaughtException', (e) => {
  restaurerTerminal()
  process.stderr.write(`\nErreur du lanceur : ${e.stack ?? e}\n`)
  process.exit(1)
})

ecran.ouvrir()
for (const s of services) {
  if (!options.seulement || options.seulement.includes(s.nom)) s.demarrer()
}
if (preparation.etat === 'avert') {
  ecran.flash(`préparation : ${preparation.avertissements} avertissement(s), voir le panneau 1`, '\x1b[33m', 6000)
}
