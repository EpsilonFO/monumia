// Préparation du dépôt avant de lancer les serveurs : tout ce qu'il faut pour
// qu'un `git pull` ou un worktree neuf démarre sans rien faire à la main.
//
// Chaque étape rend un verdict : ✓ (rien à dire), ⚠ (on peut lancer, mais
// quelque chose cloche) ou ✖ (un serveur ne pourra pas tourner). Seul un ✖
// arrête le lancement, et encore : on propose de continuer.

import { spawn, spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { Journal } from './services.mjs'

const FICHIERS_ENV = [
  'backend/.env',
  'backend/.env.local',
  'frontend/.env',
  'frontend/.env.local',
  'landing/.env',
  'landing/.env.local',
]
// Ceux sans lesquels le dev local ne tourne pas ; scripts/setup-env-local.sh
// sait les générer depuis `supabase status`.
const ENV_INDISPENSABLES = ['backend/.env.local', 'frontend/.env.local', 'landing/.env.local']

// Empreinte du package-lock.json avec lequel node_modules a été installé.
const TEMOIN_NODE = '.monumia-lock'

const C = {
  gras: '\x1b[1m',
  pale: '\x1b[2m',
  vert: '\x1b[32m',
  jaune: '\x1b[33m',
  rouge: '\x1b[31m',
  cyan: '\x1b[36m',
  raz: '\x1b[0m',
}

export class Preparation {
  constructor({ racine, principal, options, ports }) {
    this.nom = 'préparation'
    this.racine = racine
    this.principal = principal
    this.estWorktree = racine !== principal
    this.options = options
    this.ports = ports
    this.journal = new Journal()
    this.etat = 'arrete'
    this.depuis = null
    this.erreursNonLues = 0
    this.vu = true
    this.echo = false
    // Ports de supabase/config.toml, précisés par `supabase status` à la préparation.
    this.liens = { studio: 'http://127.0.0.1:54323', mailpit: 'http://127.0.0.1:54324' }
    this.descriptionCommande = 'préparation du dépôt (r pour la relancer)'
    this.surChangement = () => {}
    this.journal.surAjout = () => this.surChangement()
  }

  // --- sortie -------------------------------------------------------------

  ecrire(ligne) {
    this.journal.ajouter(ligne)
    if (this.echo) process.stdout.write(ligne + '\n')
  }

  titre(nom) {
    this.ecrire(`${C.gras}▸ ${nom}${C.raz}`)
  }

  detail(texte) {
    this.ecrire(`  ${C.pale}${texte}${C.raz}`)
  }

  ok(texte) {
    this.ecrire(`  ${C.vert}✓${C.raz} ${texte}`)
  }

  avert(texte) {
    this.avertissements++
    this.ecrire(`  ${C.jaune}⚠ ${texte}${C.raz}`)
  }

  echec(texte) {
    this.echecs++
    this.ecrire(`  ${C.rouge}✖ ${texte}${C.raz}`)
  }

  // --- orchestration ------------------------------------------------------

  /**
   * @param {object} p
   * @param {((question: string) => Promise<boolean>) | null} p.demander
   *   pose une question oui/non ; `null` quand personne ne peut répondre
   *   (relance depuis l'écran), et la réponse vaut alors « non ».
   */
  async executer({ demander = null } = {}) {
    this.avertissements = 0
    this.echecs = 0
    this.demander = demander
    this.etat = 'demarrage'
    this.depuis = Date.now()
    this.surChangement()
    const debut = Date.now()

    await this.etape('Dépôt', () => this.depot())
    const supabaseOk = await this.etape('Supabase local', () => this.supabase())
    await this.etape("Variables d'environnement", () => this.env(supabaseOk))
    await this.etape('Migrations (base locale)', () => this.migrations(supabaseOk))
    await this.etape('Backend · uv sync', () => this.python())
    await this.etape('Frontend · node_modules', () => this.node('frontend'))
    await this.etape('Landing · node_modules', () => this.node('landing'))
    await this.etape('Ports', () => this.verifierPorts())

    const duree = ((Date.now() - debut) / 1000).toFixed(1)
    const bilan =
      this.echecs > 0
        ? `${C.rouge}${this.echecs} échec(s)${C.raz}`
        : this.avertissements > 0
          ? `${C.jaune}${this.avertissements} avertissement(s)${C.raz}`
          : `${C.vert}tout est prêt${C.raz}`
    this.ecrire('')
    this.ecrire(`${C.gras}Préparation terminée en ${duree} s${C.raz} · ${bilan}`)
    this.etat = this.echecs > 0 ? 'echec' : this.avertissements > 0 ? 'avert' : 'pret'
    this.depuis = Date.now()
    this.surChangement()
    return { echecs: this.echecs, avertissements: this.avertissements }
  }

  /** Rend `true` si l'étape s'est terminée sans échec. */
  async etape(nom, fn) {
    this.titre(nom)
    const avant = this.echecs
    try {
      await fn()
    } catch (e) {
      this.echec(e.message)
    }
    return this.echecs === avant
  }

  // --- étapes -------------------------------------------------------------

  async depot() {
    const branche = git(this.racine, 'rev-parse', '--abbrev-ref', 'HEAD') || '?'
    this.detail(
      this.estWorktree
        ? `worktree ${path.relative(this.principal, this.racine)} · branche ${branche}`
        : `dépôt principal · branche ${branche}`,
    )

    const modifs = (git(this.racine, 'status', '--porcelain') || '').split('\n').filter(Boolean).length
    if (modifs > 0) this.detail(`${modifs} fichier(s) modifié(s) non commités`)

    const fetch = await this.commande('git', ['fetch', '--quiet'], {
      silencieux: true,
      timeout: 10000,
      env: { GIT_TERMINAL_PROMPT: '0', GIT_SSH_COMMAND: 'ssh -o BatchMode=yes -o ConnectTimeout=5' },
    })
    if (fetch.code !== 0) {
      this.avert('git fetch impossible (hors ligne ?) : fraîcheur par rapport à GitHub non vérifiée')
      return
    }

    const amont = git(this.racine, 'rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')
    const reference = amont || 'origin/main'
    const compte = git(this.racine, 'rev-list', '--left-right', '--count', `HEAD...${reference}`)
    if (!compte) {
      this.ok(`branche ${branche}`)
      return
    }
    const [avance, retard] = compte.split(/\s+/).map(Number)
    if (retard > 0 && amont) {
      this.avert(`${retard} commit(s) de retard sur ${reference} : un git pull s'impose`)
    } else if (retard > 0) {
      this.ok(`${reference} a avancé de ${retard} commit(s) depuis le départ de cette branche`)
    } else {
      this.ok(`à jour avec ${reference}${avance > 0 ? ` (${avance} commit(s) d'avance)` : ''}`)
    }
  }

  async supabase() {
    let statut = await this.commande('supabase', ['status', '-o', 'env'], { silencieux: true })
    if (statut.code === -2) throw new Error('CLI Supabase introuvable : https://supabase.com/docs/guides/cli')
    if (statut.code !== 0) {
      this.detail('stack arrêtée, démarrage (la première fois : quelques minutes)…')
      const demarrage = await this.commande('supabase', ['start'])
      if (demarrage.code !== 0) throw new Error('supabase start a échoué : Docker tourne-t-il ?')
      statut = await this.commande('supabase', ['status', '-o', 'env'], { silencieux: true })
    }
    const lire = (cle) => statut.sortie.match(new RegExp(`^${cle}="?([^"\\n]*)"?`, 'm'))?.[1]
    this.liens = {
      studio: lire('STUDIO_URL'),
      mailpit: lire('MAILPIT_URL') ?? lire('INBUCKET_URL'),
    }
    this.ok(`en marche · ${lire('API_URL') ?? '?'}${this.liens.studio ? ` · Studio ${this.liens.studio}` : ''}`)
  }

  async env(supabaseOk) {
    if (this.estWorktree) {
      const copies = []
      for (const f of FICHIERS_ENV) {
        const cible = path.join(this.racine, f)
        const source = path.join(this.principal, f)
        if (!fs.existsSync(cible) && fs.existsSync(source)) {
          fs.copyFileSync(source, cible)
          copies.push(f)
        }
      }
      if (copies.length) this.detail(`copiés depuis le dépôt principal : ${copies.join(', ')}`)
    }

    const manquants = ENV_INDISPENSABLES.filter((f) => !fs.existsSync(path.join(this.racine, f)))
    if (manquants.length === 0) {
      this.ok(ENV_INDISPENSABLES.map((f) => path.basename(path.dirname(f))).join(', ') + ' : .env.local présents')
      return
    }
    if (!supabaseOk) throw new Error(`${manquants.join(', ')} absent(s), et impossible de les générer sans Supabase`)
    this.detail(`${manquants.join(', ')} absent(s) : génération depuis supabase status`)
    const r = await this.commande('bash', [path.join(this.racine, 'scripts', 'setup-env-local.sh')])
    if (r.code !== 0) throw new Error('scripts/setup-env-local.sh a échoué')
    this.avert(
      'fichiers générés avec les seules clés Supabase : les clés tierces (Stripe, Resend…) sont à reporter depuis backend/.env.example',
    )
  }

  async migrations(supabaseOk) {
    if (this.options.sansDb) {
      this.detail('ignorées (--sans-db)')
      return
    }
    if (!supabaseOk) {
      this.avert('ignorées : Supabase local indisponible')
      return
    }
    const r = await this.commande('supabase', ['db', 'push', '--local', '--include-all', '--yes'])
    if (r.code === 0) {
      this.ok(/up to date/i.test(r.sortie) ? 'base locale à jour' : 'migrations appliquées')
      return
    }
    if (/not found in local migrations directory/i.test(r.sortie)) {
      this.avert(
        this.estWorktree
          ? "la base locale a des migrations qu'ignore cette branche (plus ancienne que main ?) : rien n'a été appliqué"
          : "la base locale a des migrations absentes de supabase/migrations : rien n'a été appliqué",
      )
    } else {
      this.avert('supabase db push a échoué : voir le détail ci-dessus')
    }
  }

  async python() {
    const backend = path.join(this.racine, 'backend')
    // `uv sync` est exact : sans --group pipeline il DÉSINSTALLERAIT providall.
    const complet = await this.commande('uv', ['sync', '--group', 'dev', '--group', 'pipeline'], { cwd: backend })
    if (complet.code === -2) throw new Error('uv introuvable : https://docs.astral.sh/uv/')
    if (complet.code === 0) {
      this.ok('venv à jour (groupes dev + pipeline)')
      return
    }
    if (fs.existsSync(path.join(backend, '.venv'))) {
      this.avert('uv sync a échoué (providall inaccessible ? hors ligne ?) : venv existant conservé tel quel')
      return
    }
    const partiel = await this.commande('uv', ['sync', '--group', 'dev'], { cwd: backend })
    if (partiel.code !== 0) throw new Error('uv sync a échoué')
    this.avert('installé sans le groupe pipeline (providall inaccessible) : scripts/ingerer.py et prospecter.py ne tourneront pas')
  }

  async node(paquet) {
    const dossier = path.join(this.racine, paquet)
    const nm = path.join(dossier, 'node_modules')
    const empreinte = empreinteLock(dossier)
    if (!empreinte) throw new Error(`${paquet}/package-lock.json introuvable`)

    // Un lien vers le node_modules du dépôt principal (posé par
    // scripts/tsc-check.sh) suffit à tsc, pas à Vite : il refuse de servir
    // les polices @fontsource situées hors du dossier du projet. On le
    // remplace par une vraie copie.
    if (estLien(nm)) {
      fs.unlinkSync(nm)
      this.detail('lien symbolique vers le dépôt principal remplacé par une copie')
    }

    if (fs.existsSync(nm) && lireTemoin(nm) === empreinte) {
      this.ok('à jour')
      return
    }

    if (!fs.existsSync(nm) && this.estWorktree && process.platform === 'darwin') {
      const source = path.join(this.principal, paquet, 'node_modules')
      const lockIdentique = empreinteLock(path.join(this.principal, paquet)) === empreinte
      const temoinSource = fs.existsSync(source) ? lireTemoin(source) : undefined
      if (lockIdentique && fs.existsSync(source) && !estLien(source) && (temoinSource ?? empreinte) === empreinte) {
        // cp -c : clonefile(2) d'APFS, copie instantanée et sans place disque
        // tant que rien n'est modifié.
        const r = await this.commande('cp', ['-cR', source, nm], { silencieux: true })
        if (r.code === 0) {
          fs.rmSync(path.join(nm, '.vite'), { recursive: true, force: true })
          ecrireTemoin(nm, empreinte)
          this.ok('cloné depuis le dépôt principal (même package-lock.json)')
          return
        }
        fs.rmSync(nm, { recursive: true, force: true })
        this.detail('clonage impossible, installation complète')
      }
    }

    this.detail(fs.existsSync(nm) ? 'package-lock.json a changé depuis la dernière installation : npm ci' : 'npm ci')
    const r = await this.commande('npm', ['ci', '--no-audit', '--no-fund'], { cwd: dossier })
    if (r.code !== 0) throw new Error(`npm ci a échoué dans ${paquet}/`)
    ecrireTemoin(nm, empreinte)
    this.ok('installé')
  }

  async verifierPorts() {
    let occupes = 0
    for (const { port, nom } of this.ports) {
      const pids = occupantsDuPort(port)
      if (pids.length === 0) continue
      const commande = commandeDe(pids[0])
      const qui = `PID ${pids.join(', ')} (${commande})`
      if (this.demander && (await this.demander(`Port ${port} (${nom}) occupé par ${qui}. Le libérer ? [o/N] `))) {
        await liberer(pids)
        if (occupantsDuPort(port).length === 0) {
          this.ok(`port ${port} libéré`)
          continue
        }
      }
      occupes++
      this.avert(`port ${port} occupé par ${qui} : ${nom} ne pourra pas démarrer`)
    }
    if (occupes === 0) this.ok(this.ports.map((p) => p.port).join(', ') + ' libres')
  }

  // --- utilitaires --------------------------------------------------------

  /**
   * Lance une commande et relaie sa sortie ligne à ligne sous l'étape en
   * cours. Rend `{ code, sortie }` ; `code` vaut -2 si la commande n'existe
   * pas, -1 si elle a été tuée (délai dépassé).
   */
  commande(commande, args, { cwd = this.racine, env = {}, timeout, silencieux = false } = {}) {
    return new Promise((resoudre) => {
      let sortie = ''
      let reste = ''
      let fini = false
      const relayer = (d) => {
        sortie += d
        if (silencieux) return
        const parts = (reste + d).split('\n')
        reste = parts.pop()
        for (const p of parts) this.ecrire(`  ${C.pale}│${C.raz} ${p.replace(/\r$/, '')}`)
      }
      const finir = (code) => {
        if (fini) return
        fini = true
        if (reste && !silencieux) this.ecrire(`  ${C.pale}│${C.raz} ${reste}`)
        resoudre({ code, sortie })
      }
      // Sans VIRTUAL_ENV : un venv activé dans le terminal ferait râler uv.
      const { VIRTUAL_ENV, ...base } = process.env
      const enfant = spawn(commande, args, {
        cwd,
        env: { ...base, ...env },
        stdio: ['ignore', 'pipe', 'pipe'],
        timeout,
      })
      enfant.stdout.setEncoding('utf8')
      enfant.stderr.setEncoding('utf8')
      enfant.stdout.on('data', relayer)
      enfant.stderr.on('data', relayer)
      enfant.on('error', (e) => finir(e.code === 'ENOENT' ? -2 : -1))
      enfant.on('close', (code) => finir(code ?? -1))
    })
  }
}

function git(cwd, ...args) {
  const r = spawnSync('git', args, { cwd, encoding: 'utf8' })
  return r.status === 0 ? r.stdout.trim() : ''
}

function empreinteLock(dossier) {
  try {
    return createHash('sha1').update(fs.readFileSync(path.join(dossier, 'package-lock.json'))).digest('hex')
  } catch {
    return null
  }
}

function lireTemoin(nm) {
  try {
    return fs.readFileSync(path.join(nm, TEMOIN_NODE), 'utf8').trim()
  } catch {
    return undefined
  }
}

function ecrireTemoin(nm, empreinte) {
  fs.writeFileSync(path.join(nm, TEMOIN_NODE), empreinte + '\n')
}

function estLien(p) {
  try {
    return fs.lstatSync(p).isSymbolicLink()
  } catch {
    return false
  }
}

function occupantsDuPort(port) {
  const r = spawnSync('lsof', ['-nP', `-iTCP:${port}`, '-sTCP:LISTEN', '-t'], { encoding: 'utf8' })
  return [...new Set((r.stdout || '').split('\n').filter(Boolean).map(Number))]
}

function commandeDe(pid) {
  const r = spawnSync('ps', ['-o', 'command=', '-p', String(pid)], { encoding: 'utf8' })
  const c = (r.stdout || '').trim()
  return c.length > 70 ? c.slice(0, 69) + '…' : c || '?'
}

async function liberer(pids) {
  for (const pid of pids) {
    try {
      process.kill(pid, 'SIGTERM')
    } catch {
      // déjà parti
    }
  }
  const debut = Date.now()
  while (Date.now() - debut < 3000) {
    if (pids.every((pid) => !vivant(pid))) return
    await new Promise((r) => setTimeout(r, 100))
  }
  for (const pid of pids) {
    try {
      process.kill(pid, 'SIGKILL')
    } catch {
      // déjà parti
    }
  }
  await new Promise((r) => setTimeout(r, 300))
}

function vivant(pid) {
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}
