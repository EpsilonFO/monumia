// L'écran plein terminal : la liste des serveurs à gauche, le journal du
// serveur choisi à droite, les raccourcis en bas.
//
// Le suivi de la souris est activé (molette, clic, glisser) : le terminal ne
// sélectionne donc plus le texte lui-même, c'est l'écran qui le fait, et `c`
// copie la sélection. Pour retrouver la sélection native du terminal, garder
// Option (⌥) enfoncé pendant le glisser (iTerm2, Terminal.app, VS Code).

import { spawn } from 'node:child_process'
import { ajuster, largeurTexte, style as S } from './ansi.mjs'

const LARGEUR_LISTE = 26

// Rangée des chiffres d'un clavier AZERTY, sans Maj : la liste affiche le
// chiffre gravé sur la touche, la touche envoie le caractère. Les chiffres
// eux-mêmes (Maj sur AZERTY, direct sur QWERTY) marchent aussi.
const TOUCHES_PANNEAUX = ['&', 'é', '"', "'", '(', '-', 'è', '_', 'ç']

const ETATS = {
  arrete: { puce: '○', couleur: S.gris, libelle: 'arrêté' },
  demarrage: { puce: '◌', couleur: S.jaune, libelle: 'démarrage…' },
  pret: { puce: '●', couleur: S.vert, libelle: 'prêt' },
  recharge: { puce: '◌', couleur: S.cyan, libelle: 'rechargement…' },
  arret: { puce: '◌', couleur: S.jaune, libelle: 'arrêt…' },
  termine: { puce: '○', couleur: S.jaune, libelle: 'terminé' },
  plante: { puce: '✖', couleur: S.rouge, libelle: 'planté' },
  avert: { puce: '▲', couleur: S.jaune, libelle: 'avertissements' },
  echec: { puce: '✖', couleur: S.rouge, libelle: 'échec' },
}

export class Ecran {
  /**
   * @param {object} p
   * @param {import('./preparation.mjs').Preparation} p.preparation
   * @param {import('./services.mjs').Service[]} p.services
   * @param {string} p.entete  texte de la barre du haut (dépôt, branche)
   */
  constructor({ preparation, services, entete }) {
    this.preparation = preparation
    this.services = services
    this.panneaux = [preparation, ...services]
    this.entete = entete
    this.actif = 1
    this.selection = null
    this.message = null
    this.carte = { journal: [], liste: [] }
    this.dernierClic = { t: 0, y: -1, x: -1 }
    this.renduPrevu = false
    this.quitte = false
    for (const p of this.panneaux) {
      p.vue = null // null : suit la fin du journal
      p.surChangement = () => this.planifierRendu()
    }
    this.marquerVu()
  }

  // --- cycle de vie ---------------------------------------------------------

  ouvrir() {
    const out = process.stdout
    // Écran alternatif, curseur masqué, souris (clic + glisser + molette) en
    // encodage SGR, collage encadré.
    out.write('\x1b[?1049h\x1b[?25l\x1b[?1000h\x1b[?1002h\x1b[?1006h\x1b[?2004h')
    process.stdin.setRawMode(true)
    process.stdin.setEncoding('utf8')
    process.stdin.resume()
    process.stdin.on('data', (d) => this.clavier(d))
    out.on('resize', () => this.rendre())
    this.horloge = setInterval(() => this.planifierRendu(), 1000)
    this.rendre()
  }

  fermer() {
    clearInterval(this.horloge)
    restaurerTerminal()
  }

  // --- rendu ----------------------------------------------------------------

  planifierRendu() {
    if (this.renduPrevu || this.quitte) return
    this.renduPrevu = true
    setTimeout(() => {
      this.renduPrevu = false
      this.rendre()
    }, 30)
  }

  get dimensions() {
    const W = Math.max(process.stdout.columns || 80, 40)
    const H = Math.max(process.stdout.rows || 24, 10)
    const xJournal = LARGEUR_LISTE + 2 // après la liste et le séparateur
    return { W, H, xJournal, wJournal: W - xJournal, hCorps: H - 3 }
  }

  rendre() {
    if (this.quitte) return
    const { W, H, wJournal, hCorps } = this.dimensions
    const panneau = this.panneaux[this.actif]
    const liste = this.rendreListe(hCorps)
    const journal = this.rendreJournal(panneau, hCorps, wJournal)

    let sortie = '\x1b[?2026h'
    sortie += `\x1b[1;1H${this.rendreEntete(W)}`
    for (let y = 0; y < hCorps; y++) {
      sortie += `\x1b[${y + 2};1H${liste[y]}${S.gris}│${S.raz} ${journal[y]}`
    }
    sortie += `\x1b[${H - 1};1H${this.rendreInfo(panneau, W, hCorps, wJournal)}`
    sortie += `\x1b[${H};1H${this.rendreRaccourcis(W)}`
    sortie += '\x1b[?2026l'
    process.stdout.write(sortie)
  }

  rendreEntete(W) {
    const gauche = ' monumia · dev '
    const droite = `${this.entete} `
    const place = W - largeurTexte(gauche)
    const aligne = largeurTexte(droite) <= place ? ' '.repeat(place - largeurTexte(droite)) + droite : ajuster(droite, place)
    return `${S.inverse}${S.gras}${gauche}${S.raz}${S.inverse}${aligne}${S.raz}`
  }

  rendreListe(h) {
    const w = LARGEUR_LISTE
    const lignes = []
    const carte = []
    const pousser = (texte, action = null) => {
      lignes.push(texte)
      carte.push(action)
    }
    pousser(' '.repeat(w))
    this.panneaux.forEach((p, i) => {
      const e = ETATS[p.etat] ?? ETATS.arrete
      const choisi = i === this.actif
      const marque = choisi ? `${S.cyan}▌${S.raz}` : ' '
      const nom = ajuster(`${i + 1} ${p.nom}`, w - 10)
      const port = p.port ? `:${p.port}` : ''
      pousser(
        `${marque}${e.couleur}${e.puce}${S.raz} ${choisi ? S.gras : ''}${nom}${S.raz}${S.gris}${port.padStart(6)}${S.raz} `,
        { panneau: i },
      )
      let detail = e.libelle
      if (p.depuis && ['pret', 'avert', 'echec', 'plante', 'termine'].includes(p.etat)) detail += ` · ${duree(p.depuis)}`
      const alerte = p.erreursNonLues > 0 ? `${S.rouge}${Math.min(p.erreursNonLues, 999)} err.${S.raz}` : ''
      const wAlerte = largeurTexte(alerte.replace(/\x1b\[[0-9;]*m/g, ''))
      pousser(`${marque}  ${S.gris}${ajuster(detail, w - 4 - wAlerte)}${S.raz}${alerte} `, { panneau: i })
      pousser(' '.repeat(w))
    })

    const liens = [
      ['API /docs', 'http://localhost:8000/docs'],
      ['Studio', this.preparation.liens.studio],
      ['Mailpit', this.preparation.liens.mailpit],
    ].filter(([, url]) => url)
    const blocLiens = [[`${S.gris} liens (clic pour ouvrir)${S.raz}`, null]]
    for (const [nom, url] of liens) {
      blocLiens.push([` ${S.bleu}${ajuster(nom, 10)}${S.raz}${S.gris}${ajuster(url.replace(/^https?:\/\//, ''), w - 11)}${S.raz}`, { url }])
    }
    while (lignes.length < h - blocLiens.length) pousser(' '.repeat(w))
    for (const [texte, action] of blocLiens) pousser(ajusterStyle(texte, w), action)
    this.carte.liste = carte.slice(0, h)
    return lignes.slice(0, h).map((l) => ajusterStyle(l, w))
  }

  rendreJournal(p, h, w) {
    // Vue figée par un clic, mais toujours collée au bas : on reprend le suivi
    // dès qu'il n'y a plus de sélection à protéger.
    if (p.vue !== null && !this.selection && rangeesSous(p, w, h) <= 0) p.vue = null
    const rangees = rangeesVisibles(p, h, w)
    this.carte.journal = rangees
    const sel = this.selection?.panneau === this.actif ? bornesSelection(this.selection) : null
    const lignes = rangees.map((r) => rendreRangee(p.journal.ligne(r.id), r, w, sel))
    while (lignes.length < h) lignes.push(' '.repeat(w))
    if (p.journal.lignes.length === 0) {
      lignes[0] = ajuster(`${p.enMarche === false && p.etat === 'arrete' ? '  arrêté — r pour lancer' : '  (journal vide)'}`, w)
      lignes[0] = `${S.gris}${lignes[0]}${S.raz}`
    }
    return lignes
  }

  rendreInfo(p, W, h, w) {
    if (this.message && Date.now() < this.message.jusqua) {
      return ajusterStyle(` ${this.message.couleur}${this.message.texte}${S.raz}`, W)
    }
    let droite = ''
    if (p.vue !== null) {
      const plusBas = rangeesSous(p, w, h)
      droite = `${S.jaune} ↑ défilement · ${plusBas} ligne(s) plus bas · Fin pour suivre ${S.raz}`
    }
    const wDroite = largeurTexte(droite.replace(/\x1b\[[0-9;]*m/g, ''))
    const gauche = ` ${S.gris}${ajuster(`$ ${p.descriptionCommande}${p.dossier ? `   (${p.dossier}/)` : ''}`, W - wDroite - 1)}${S.raz}`
    return ajusterStyle(gauche + droite, W)
  }

  rendreRaccourcis(W) {
    const surPrep = this.actif === 0
    const touches = [
      ['↑↓', 'serveur'],
      ['r', surPrep ? 'relancer la préparation' : 'relancer'],
      ...(surPrep ? [] : [['x', 'arrêter']]),
      ['R', 'tout relancer'],
      ['c', 'copier la sélection'],
      ['C', 'copier tout'],
      ['o', 'ouvrir'],
      ['e', 'effacer'],
      ['⇞⇟', 'défiler'],
      ['q', 'quitter'],
    ]
    let sortie = ''
    let largeur = 0
    for (const [t, l] of touches) {
      const bloc = ` ${t} ${l} `
      const wb = largeurTexte(bloc) + 1
      if (largeur + wb > W) break
      sortie += `${S.inverse} ${t} ${S.raz}${S.gris} ${l} ${S.raz}`
      largeur += wb
    }
    return sortie + ' '.repeat(Math.max(W - largeur, 0))
  }

  // --- actions --------------------------------------------------------------

  flash(texte, couleur = S.vert, duree = 2500) {
    this.message = { texte, couleur, jusqua: Date.now() + duree }
    this.planifierRendu()
    setTimeout(() => this.planifierRendu(), duree + 50)
  }

  choisir(i) {
    if (i < 0 || i >= this.panneaux.length || i === this.actif) return
    this.actif = i
    this.selection = null
    this.marquerVu()
    this.planifierRendu()
  }

  marquerVu() {
    this.panneaux.forEach((p, i) => {
      p.vu = i === this.actif
      if (p.vu) p.erreursNonLues = 0
    })
  }

  async relancerActif() {
    if (this.actif === 0) return this.relancerPreparation()
    const s = this.panneaux[this.actif]
    this.flash(`${s.nom} : ${s.enMarche ? 'relance' : 'lancement'}…`, S.cyan)
    await s.relancer()
  }

  async relancerPreparation() {
    const p = this.preparation
    if (p.etat === 'demarrage') return
    // npm ci sous un Vite qui tourne, ou uv sync sous uvicorn : on arrête
    // d'abord, on relance ensuite ceux qui tournaient.
    const aRelancer = this.services.filter((s) => s.enMarche)
    if (aRelancer.length) this.flash(`arrêt de ${aRelancer.map((s) => s.nom).join(', ')} le temps de la préparation…`, S.jaune)
    await Promise.all(aRelancer.map((s) => s.arreter()))
    p.journal.ajouter('')
    p.journal.ajouter(`${S.gris}── nouvelle préparation · ${new Date().toLocaleTimeString('fr-FR')} ──${S.raz}`)
    const { echecs } = await p.executer({ demander: null })
    for (const s of aRelancer) s.demarrer()
    if (echecs > 0) this.flash('préparation : échec, voir le panneau', S.rouge, 4000)
    else if (aRelancer.length) this.flash(`préparation faite, ${aRelancer.map((s) => s.nom).join(', ')} relancé(s)`)
  }

  async toutRelancer() {
    this.flash('relance de tous les serveurs…', S.cyan)
    await Promise.all(this.services.map((s) => s.relancer()))
  }

  arreterActif() {
    const s = this.panneaux[this.actif]
    if (this.actif === 0 || !s.enMarche) return
    this.flash(`${s.nom} : arrêt…`, S.jaune)
    s.arreter()
  }

  copier(tout) {
    const p = this.panneaux[this.actif]
    let texte
    if (tout) {
      const ids = []
      for (let id = p.journal.premier; id < p.journal.fin; id++) ids.push(p.journal.texteDe(id))
      texte = ids.join('\n')
    } else {
      if (!this.selection || this.selection.panneau !== this.actif) {
        this.flash('rien de sélectionné : glisser à la souris sur le journal (double-clic : une ligne)', S.jaune)
        return
      }
      texte = texteSelection(p, this.selection)
    }
    if (!texte) {
      this.flash('rien à copier', S.jaune)
      return
    }
    copierPressePapiers(texte)
    const n = texte.split('\n').length
    this.flash(`copié : ${n} ligne(s), ${texte.length} caractère(s)`)
    this.selection = null
  }

  ouvrirLien(url) {
    const p = this.panneaux[this.actif]
    url ??= p.url ?? this.preparation.liens.studio
    if (!url) return
    const cmd = process.platform === 'darwin' ? 'open' : 'xdg-open'
    spawn(cmd, [url], { stdio: 'ignore', detached: true }).on('error', () => {}).unref()
    this.flash(`ouverture de ${url}`, S.cyan)
  }

  effacer() {
    const p = this.panneaux[this.actif]
    p.journal.effacer()
    p.vue = null
    this.selection = null
    this.planifierRendu()
  }

  defiler(n) {
    const { wJournal, hCorps } = this.dimensions
    defiler(this.panneaux[this.actif], n, wJournal, hCorps)
    this.planifierRendu()
  }

  async quitter() {
    if (this.quitte) return
    this.quitte = true
    this.fermer()
    const enMarche = this.services.filter((s) => s.enMarche)
    if (enMarche.length) process.stdout.write(`Arrêt de ${enMarche.map((s) => s.nom).join(', ')}…\n`)
    await Promise.all(enMarche.map((s) => s.arreter()))
    process.exit(0)
  }

  // --- entrées --------------------------------------------------------------

  clavier(donnees) {
    for (const t of decouperEntrees(donnees)) {
      if (t.souris) this.souris(t)
      else this.touche(t.touche)
    }
  }

  touche(k) {
    const { hCorps } = this.dimensions
    switch (k) {
      case 'q':
      case '\x03':
        return this.quitter()
      case 'up':
      case 'k':
      case 'S-tab':
        return this.choisir((this.actif + this.panneaux.length - 1) % this.panneaux.length)
      case 'down':
      case 'j':
      case '\t':
        return this.choisir((this.actif + 1) % this.panneaux.length)
      case 'r':
        return this.relancerActif()
      case 'R':
        return this.toutRelancer()
      case 'x':
        return this.arreterActif()
      case 'c':
        return this.copier(false)
      case 'C':
        return this.copier(true)
      case 'o':
        return this.ouvrirLien()
      case 'e':
        return this.effacer()
      case 'pgup':
      case 'u':
        return this.defiler(-(hCorps - 1))
      case 'pgdn':
      case 'd':
      case ' ':
        return this.defiler(hCorps - 1)
      case 'S-up':
        return this.defiler(-1)
      case 'S-down':
        return this.defiler(1)
      case 'home':
      case 'g':
        return this.defiler(-Infinity)
      case 'end':
      case 'G':
        this.panneaux[this.actif].vue = null
        return this.planifierRendu()
      case 'esc':
        this.selection = null
        return this.planifierRendu()
      default:
        if (TOUCHES_PANNEAUX.includes(k)) return this.choisir(TOUCHES_PANNEAUX.indexOf(k))
        if (/^[1-9]$/.test(k)) return this.choisir(Number(k) - 1)
    }
  }

  souris({ bouton, x, y, relache }) {
    const { xJournal, hCorps } = this.dimensions
    const yCorps = y - 2 // la première rangée du corps est la ligne 2 du terminal
    const dansJournal = x > xJournal && yCorps >= 0 && yCorps < hCorps
    const base = bouton & ~(4 | 8 | 16) // sans Maj/Méta/Ctrl

    if (base === 64 || base === 65) {
      if (x > xJournal) this.defiler(base === 64 ? -3 : 3)
      return
    }

    // Glisser (bouton gauche + mouvement)
    if (base === 32) {
      if (!this.selection?.enCours) return
      if (yCorps < 0) this.defiler(-1)
      else if (yCorps >= hCorps) this.defiler(1)
      const pos = this.positionTexte(Math.min(Math.max(yCorps, 0), hCorps - 1), x - xJournal - 1)
      if (pos) this.selection.b = pos
      return this.planifierRendu()
    }

    if (base !== 0) return

    if (relache) {
      if (this.selection?.enCours) {
        this.selection.enCours = false
        const { a, b } = this.selection
        if (a.id === b.id && a.c === b.c) this.selection = null
        this.planifierRendu()
      }
      return
    }

    // Clic dans la liste : choisir un serveur ou ouvrir un lien.
    if (x <= LARGEUR_LISTE && yCorps >= 0 && yCorps < hCorps) {
      const action = this.carte.liste[yCorps]
      if (action?.panneau !== undefined) this.choisir(action.panneau)
      else if (action?.url) this.ouvrirLien(action.url)
      return
    }

    if (!dansJournal) return
    const p = this.panneaux[this.actif]
    const pos = this.positionTexte(yCorps, x - xJournal - 1)
    if (!pos) {
      this.selection = null
      return this.planifierRendu()
    }
    // Figer la vue : le texte ne doit pas défiler sous la souris quand des
    // lignes arrivent pendant qu'on sélectionne.
    if (p.vue === null && this.carte.journal.length) {
      const haut = this.carte.journal[0]
      p.vue = { id: haut.id, k: haut.k }
    }
    const maintenant = Date.now()
    const double = maintenant - this.dernierClic.t < 400 && this.dernierClic.y === y && Math.abs(this.dernierClic.x - x) <= 1
    this.dernierClic = { t: maintenant, y, x }
    if (double) {
      const longueur = p.journal.ligne(pos.id)?.texte.length ?? 0
      this.selection = { panneau: this.actif, a: { id: pos.id, c: 0 }, b: { id: pos.id, c: longueur }, enCours: false }
    } else {
      this.selection = { panneau: this.actif, a: pos, b: pos, enCours: true }
    }
    this.planifierRendu()
  }

  /** Rangée d'écran + colonne dans le journal → position dans le texte. */
  positionTexte(yCorps, colonne) {
    const rangees = this.carte.journal
    if (rangees.length === 0) return null
    if (yCorps >= rangees.length) {
      const r = rangees[rangees.length - 1]
      return { id: r.id, c: r.fin }
    }
    const r = rangees[yCorps]
    const ligne = this.panneaux[this.actif].journal.ligne(r.id)
    let col = 0
    for (let i = r.debut; i < r.fin; i++) {
      const w = ligne.larg[i]
      if (colonne < col + w) return { id: r.id, c: i }
      col += w
    }
    return { id: r.id, c: r.fin }
  }
}

// --- journal : découpage en rangées -----------------------------------------

/** Rangées d'écran d'une ligne pour une largeur donnée : `[[debut, fin], …]`. */
function rangeesDe(ligne, w) {
  if (ligne.cacheW === w) return ligne.cache
  const r = []
  let debut = 0
  let col = 0
  for (let i = 0; i < ligne.texte.length; i++) {
    const lw = ligne.larg[i]
    if (col + lw > w && i > debut) {
      r.push([debut, i])
      debut = i
      col = 0
    }
    col += lw
  }
  r.push([debut, ligne.texte.length])
  ligne.cache = r
  ligne.cacheW = w
  return r
}

function rangeesVisibles(p, h, w) {
  const j = p.journal
  const res = []
  if (p.vue === null) {
    for (let id = j.fin - 1; id >= j.premier && res.length < h; id--) {
      const rs = rangeesDe(j.ligne(id), w)
      for (let k = rs.length - 1; k >= 0 && res.length < h; k--) res.push({ id, k, debut: rs[k][0], fin: rs[k][1] })
    }
    return res.reverse()
  }
  if (p.vue.id < j.premier) p.vue = { id: j.premier, k: 0 }
  let k = p.vue.k
  for (let id = p.vue.id; id < j.fin && res.length < h; id++, k = 0) {
    const rs = rangeesDe(j.ligne(id), w)
    for (; k < rs.length && res.length < h; k++) res.push({ id, k, debut: rs[k][0], fin: rs[k][1] })
  }
  return res
}

/** Nombre de rangées sous le bas de la vue figée (plafonné pour rester rapide). */
function rangeesSous(p, w, h) {
  const j = p.journal
  if (p.vue === null) return 0
  let n = -h
  let k = p.vue.k
  for (let id = p.vue.id; id < j.fin; id++, k = 0) {
    n += rangeesDe(j.ligne(id), w).length - k
    if (n > 99999) break
  }
  return Math.max(n, 0)
}

function defiler(p, n, w, h) {
  const j = p.journal
  if (j.lignes.length === 0) return
  if (p.vue === null) {
    if (n >= 0) return
    const vis = rangeesVisibles(p, h, w)
    if (vis.length < h) return // tout tient à l'écran
    p.vue = { id: vis[0].id, k: vis[0].k }
  }
  let { id, k } = p.vue
  if (n === -Infinity) {
    id = j.premier
    k = 0
  } else if (n < 0) {
    for (let i = 0; i < -n; i++) {
      if (k > 0) k--
      else if (id > j.premier) {
        id--
        k = rangeesDe(j.ligne(id), w).length - 1
      } else break
    }
  } else {
    for (let i = 0; i < n; i++) {
      if (k < rangeesDe(j.ligne(id), w).length - 1) k++
      else if (id < j.fin - 1) {
        id++
        k = 0
      } else break
    }
  }
  p.vue = { id, k }
  // Revenu en bas : on reprend le suivi.
  if (rangeesSous(p, w, h) <= 0) p.vue = null
}

// --- sélection --------------------------------------------------------------

function avant(a, b) {
  return a.id < b.id || (a.id === b.id && a.c <= b.c)
}

function bornesSelection(sel) {
  return avant(sel.a, sel.b) ? { debut: sel.a, fin: sel.b } : { debut: sel.b, fin: sel.a }
}

function texteSelection(p, sel) {
  const { debut, fin } = bornesSelection(sel)
  const morceaux = []
  for (let id = Math.max(debut.id, p.journal.premier); id <= fin.id && id < p.journal.fin; id++) {
    const t = p.journal.ligne(id).texte
    const a = id === debut.id ? debut.c : 0
    const b = id === fin.id ? fin.c : t.length
    morceaux.push(t.slice(a, b).join(''))
  }
  return morceaux.join('\n')
}

function rendreRangee(ligne, r, w, sel) {
  let selA = -1
  let selB = -1
  if (sel && r.id >= sel.debut.id && r.id <= sel.fin.id) {
    selA = r.id === sel.debut.id ? sel.debut.c : 0
    selB = r.id === sel.fin.id ? sel.fin.c : Infinity
  }
  let out = ''
  let courant = null
  let run = 0
  let sgr = ''
  // Style de la ligne au début de la rangée
  while (run < ligne.runs.length && ligne.runs[run].debut <= r.debut) sgr = ligne.runs[run++].sgr
  let col = 0
  for (let i = r.debut; i < r.fin; i++) {
    while (run < ligne.runs.length && ligne.runs[run].debut <= i) sgr = ligne.runs[run++].sgr
    const voulu = sgr + (i >= selA && i < selB ? S.inverse : '')
    if (voulu !== courant) {
      out += S.raz + voulu
      courant = voulu
    }
    out += ligne.texte[i]
    col += ligne.larg[i]
  }
  // Une ligne vide sélectionnée en entier reste visible.
  if (r.debut === r.fin && selA === 0 && selB > 0 && col < w) {
    out += S.raz + S.inverse + ' '
    col++
  }
  return out + S.raz + ' '.repeat(Math.max(w - col, 0))
}

// --- entrées ----------------------------------------------------------------

const TOUCHES_CSI = {
  A: 'up',
  B: 'down',
  C: 'right',
  D: 'left',
  H: 'home',
  F: 'end',
  Z: 'S-tab',
  '5~': 'pgup',
  '6~': 'pgdn',
  '1~': 'home',
  '4~': 'end',
  '7~': 'home',
  '8~': 'end',
  '1;2A': 'S-up',
  '1;2B': 'S-down',
}

function decouperEntrees(s) {
  const res = []
  let i = 0
  // Collage encadré : ignoré en bloc, un collage ne doit pas déclencher de raccourcis.
  s = s.replace(/\x1b\[200~[\s\S]*?\x1b\[201~/g, '')
  while (i < s.length) {
    const reste = s.slice(i)
    let m
    if ((m = /^\x1b\[<(\d+);(\d+);(\d+)([Mm])/.exec(reste))) {
      res.push({ souris: true, bouton: Number(m[1]), x: Number(m[2]), y: Number(m[3]), relache: m[4] === 'm' })
    } else if ((m = /^\x1b\[([0-9;]*[A-Za-z~])/.exec(reste))) {
      res.push({ touche: TOUCHES_CSI[m[1]] ?? `csi:${m[1]}` })
    } else if ((m = /^\x1bO([A-D])/.exec(reste))) {
      res.push({ touche: TOUCHES_CSI[m[1]] })
    } else if (reste[0] === '\x1b' && reste.length === 1) {
      m = ['\x1b']
      res.push({ touche: 'esc' })
    } else if (reste[0] === '\x1b') {
      m = [reste.slice(0, 2)] // Alt+touche : ignoré
    } else {
      m = [reste[0]]
      res.push({ touche: reste[0] })
    }
    i += m[0].length
  }
  return res
}

// --- utilitaires -------------------------------------------------------------

export function restaurerTerminal() {
  try {
    process.stdout.write('\x1b[?2004l\x1b[?1006l\x1b[?1002l\x1b[?1000l\x1b[?25h\x1b[?1049l')
    if (process.stdin.isTTY) process.stdin.setRawMode(false)
    process.stdin.pause()
  } catch {
    // terminal déjà fermé
  }
}

function copierPressePapiers(texte) {
  const outil =
    process.platform === 'darwin' ? ['pbcopy', []] : process.env.WAYLAND_DISPLAY ? ['wl-copy', []] : ['xclip', ['-selection', 'clipboard']]
  let fait = false
  try {
    const p = spawn(outil[0], outil[1], { stdio: ['pipe', 'ignore', 'ignore'] })
    p.on('error', () => osc52(texte))
    p.stdin.end(texte)
    fait = true
  } catch {
    // outil absent
  }
  if (!fait) osc52(texte)
}

// Repli : le terminal lui-même met le texte au presse-papiers (marche aussi en SSH).
function osc52(texte) {
  process.stdout.write(`\x1b]52;c;${Buffer.from(texte).toString('base64')}\x07`)
}

/** Complète un texte STYLÉ à `w` colonnes (les séquences SGR ne comptent pas). */
function ajusterStyle(s, w) {
  const nu = s.replace(/\x1b\[[0-9;]*m/g, '')
  const lw = largeurTexte(nu)
  if (lw <= w) return s + ' '.repeat(w - lw)
  // Trop long : on retombe sur le texte nu, coupé.
  return ajuster(nu, w)
}

function duree(depuis) {
  const s = Math.floor((Date.now() - depuis) / 1000)
  if (s < 60) return `${s} s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} min`
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}`
}
