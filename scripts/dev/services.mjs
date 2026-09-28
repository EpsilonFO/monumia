// Les serveurs de dev et leur journal.
//
// Chaque serveur tourne dans son propre groupe de processus (`detached`) :
// `uv run uvicorn --reload` et `vite` lancent des enfants, et seul un signal au
// groupe entier les arrête tous. Sans ça, un « arrêter » laissait le worker
// uvicorn en vie, qui gardait le port 8000 et faisait échouer la relance.

import { spawn } from 'node:child_process'
import path from 'node:path'
import { analyserLigne } from './ansi.mjs'

const MAX_LIGNES = 5000

export class Journal {
  constructor() {
    this.lignes = []
    // Identifiant de la première ligne gardée : les identifiants restent
    // stables quand les plus anciennes sont jetées, la sélection et la
    // position de défilement s'y accrochent.
    this.premier = 0
    this.etatSgr = { sgr: '' }
    this.reste = ''
    this.minuteur = null
    this.surAjout = null
  }

  get fin() {
    return this.premier + this.lignes.length
  }

  ligne(id) {
    return this.lignes[id - this.premier]
  }

  /** Reçoit un morceau de flux brut ; seules les lignes complètes sont gardées. */
  ecrire(morceau) {
    const parts = (this.reste + morceau).split('\n')
    this.reste = parts.pop()
    for (const p of parts) this.ajouter(p)
    // Une invite sans retour à la ligne ne doit pas rester invisible.
    clearTimeout(this.minuteur)
    if (this.reste) this.minuteur = setTimeout(() => this.vider(), 200)
  }

  vider() {
    clearTimeout(this.minuteur)
    if (this.reste) {
      const r = this.reste
      this.reste = ''
      this.ajouter(r)
    }
  }

  ajouter(brut, { systeme = false } = {}) {
    const l = analyserLigne(brut.replace(/\r$/, ''), systeme ? { sgr: '' } : this.etatSgr)
    l.systeme = systeme
    this.lignes.push(l)
    if (this.lignes.length > MAX_LIGNES + 500) {
      this.lignes.splice(0, 500)
      this.premier += 500
    }
    this.surAjout?.(l, brut)
  }

  effacer() {
    this.premier = this.fin
    this.lignes = []
  }

  texteDe(id) {
    return this.ligne(id)?.texte.join('') ?? ''
  }
}

const RE_ERREUR = /\b(ERROR|Error|Traceback|Exception|FATAL|failed|EADDRINUSE)\b|address already in use/i

export class Service {
  /**
   * @param {object} def
   * @param {string} def.nom
   * @param {string} def.dossier  chemin relatif à la racine du dépôt
   * @param {string} def.commande
   * @param {string[]} def.args
   * @param {number} [def.port]
   * @param {string} [def.url]
   * @param {RegExp} [def.pret]      ligne qui annonce que le serveur écoute
   * @param {RegExp} [def.recharge]  ligne qui annonce un rechargement à chaud
   */
  constructor(def, racine) {
    Object.assign(this, def)
    this.racine = racine
    this.cwd = path.join(racine, def.dossier)
    this.journal = new Journal()
    this.etat = 'arrete'
    this.depuis = null
    this.enfant = null
    this.arretDemande = false
    this.erreursNonLues = 0
    this.vu = true
    this.surChangement = () => {}
    this.journal.surAjout = (l, brut) => {
      if (!l.systeme) this.analyser(brut)
      if (!this.vu && !l.systeme && RE_ERREUR.test(brut)) this.erreursNonLues++
      this.surChangement()
    }
  }

  get enMarche() {
    return this.enfant !== null
  }

  get descriptionCommande() {
    return [this.commandeAffichee ?? this.commande, ...this.args].join(' ')
  }

  analyser(brut) {
    if (this.pret?.test(brut)) this.changerEtat('pret')
    else if (this.recharge?.test(brut) && this.etat === 'pret') this.changerEtat('recharge')
  }

  changerEtat(etat) {
    if (this.etat === etat) return
    this.etat = etat
    if (etat !== 'recharge') this.depuis = Date.now()
    this.surChangement()
  }

  systeme(texte, couleur = '\x1b[2m') {
    this.journal.vider()
    this.journal.ajouter(`${couleur}── ${texte} ──\x1b[0m`, { systeme: true })
  }

  demarrer() {
    if (this.enfant) return
    this.arretDemande = false
    const env = { ...process.env, FORCE_COLOR: '1', PYTHONUNBUFFERED: '1' }
    delete env.NO_COLOR
    // Un venv activé dans le terminal ferait râler `uv run`, qui prend celui du projet.
    delete env.VIRTUAL_ENV
    let enfant
    try {
      enfant = spawn(this.commande, this.args, {
        cwd: this.cwd,
        env,
        detached: true,
        stdio: ['ignore', 'pipe', 'pipe'],
      })
    } catch (e) {
      this.systeme(`impossible de lancer : ${e.message}`, '\x1b[31m')
      this.changerEtat('plante')
      return
    }
    this.enfant = enfant
    this.changerEtat('demarrage')
    this.systeme(`lancé : ${this.descriptionCommande}  (pid ${enfant.pid ?? '?'})`, '\x1b[36m')

    enfant.stdout.setEncoding('utf8')
    enfant.stderr.setEncoding('utf8')
    enfant.stdout.on('data', (d) => this.journal.ecrire(d))
    enfant.stderr.on('data', (d) => this.journal.ecrire(d))
    enfant.on('error', (e) => {
      this.systeme(`erreur de lancement : ${e.message}`, '\x1b[31m')
    })
    enfant.on('exit', (code, signal) => {
      this.journal.vider()
      this.enfant = null
      if (this.arretDemande) {
        this.systeme('arrêté')
        this.changerEtat('arrete')
      } else if (code === 0) {
        this.systeme('terminé (code 0)', '\x1b[33m')
        this.changerEtat('termine')
      } else {
        this.systeme(`s'est arrêté (${signal ?? `code ${code}`})`, '\x1b[31m')
        this.changerEtat('plante')
      }
    })
  }

  /** Arrête le groupe entier ; se résout quand plus aucun de ses processus ne vit. */
  arreter() {
    const enfant = this.enfant
    if (!enfant) return Promise.resolve()
    this.arretDemande = true
    this.changerEtat('arret')
    const pgid = enfant.pid
    signalerGroupe(pgid, 'SIGTERM')
    return new Promise((resoudre) => {
      const debut = Date.now()
      const attendre = () => {
        const vivant = groupeVivant(pgid)
        if (!vivant && !this.enfant) return resoudre()
        if (Date.now() - debut > 4000) {
          signalerGroupe(pgid, 'SIGKILL')
          if (Date.now() - debut > 6000) return resoudre()
        }
        setTimeout(attendre, 100)
      }
      attendre()
    })
  }

  async relancer() {
    await this.arreter()
    this.demarrer()
  }

  /** Arrêt brutal et synchrone, pour la sortie du programme. */
  tuer() {
    if (this.enfant) signalerGroupe(this.enfant.pid, 'SIGKILL')
  }
}

function signalerGroupe(pgid, signal) {
  if (!pgid) return
  try {
    process.kill(-pgid, signal)
  } catch {
    // Le groupe est déjà parti.
  }
}

function groupeVivant(pgid) {
  try {
    process.kill(-pgid, 0)
    return true
  } catch {
    return false
  }
}

/**
 * Les trois serveurs. Les ports sont ceux des configurations Vite (3000 est
 * en `strictPort`) et de la commande uvicorn documentée dans CLAUDE.md.
 */
export function definirServices(racine) {
  const vite = (dossier) => path.join(racine, dossier, 'node_modules', '.bin', 'vite')
  return [
    new Service(
      {
        nom: 'backend',
        dossier: 'backend',
        commande: 'uv',
        args: ['run', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000', '--reload', '--use-colors'],
        port: 8000,
        url: 'http://localhost:8000/docs',
        pret: /Application startup complete/,
        recharge: /WatchFiles detected changes|Reloading\.\.\./,
      },
      racine,
    ),
    new Service(
      {
        nom: 'frontend',
        dossier: 'frontend',
        commande: vite('frontend'),
        commandeAffichee: 'vite',
        args: [],
        port: 3000,
        url: 'http://localhost:3000',
        pret: /ready in|Local:/,
      },
      racine,
    ),
    new Service(
      {
        nom: 'landing',
        dossier: 'landing',
        commande: vite('landing'),
        commandeAffichee: 'vite',
        args: [],
        port: 3001,
        url: 'http://localhost:3001',
        pret: /ready in|Local:/,
      },
      racine,
    ),
  ]
}
