#!/usr/bin/env node
// Liste les textes encore écrits en dur dans le code (candidats à une clé de
// traduction). Heuristique, donc à relire : un identifiant technique peut sortir,
// une chaîne d'un seul mot sans accent peut passer.
//
//   node scripts/i18n-reste.mjs [chemin…]        (défaut : src)
//   node scripts/i18n-reste.mjs --compte src      (un total par fichier)
//
// Sortent : le texte JSX, les attributs JSX lisibles (placeholder, title, alt,
// aria-*, label…), et toute chaîne littérale qui ressemble à une phrase (une
// espace et une lettre, ou une lettre accentuée). Sont ignorés : les tests, les
// imports, les classes CSS (className, cn, clsx, cva, twMerge), la console, les
// clés passées à t()/i18n.t()/Trans, les types littéraux, les clés d'objet et
// les commentaires.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

const args = process.argv.slice(2);
const compte = args.includes('--compte');
const racines = args.filter((a) => !a.startsWith('--'));
if (racines.length === 0) racines.push('src');

const ATTRIBUTS_LISIBLES = new Set([
  'placeholder', 'title', 'alt', 'label', 'aria-label', 'aria-description',
  'aria-placeholder', 'aria-roledescription', 'aria-valuetext', 'description',
  'tooltip', 'emptyMessage', 'helperText', 'heading', 'subtitle', 'caption',
]);
const APPELS_IGNORES = new Set([
  'cn', 'clsx', 'cva', 'twMerge', 'require', 'useTranslation', 'getFixedT',
  'querySelector', 'querySelectorAll', 'getElementById', 'addEventListener',
  'removeEventListener', 'matchMedia', 'createElement', 'setAttribute',
  'getAttribute', 'getItem', 'setItem', 'removeItem', 'capture', 'register',
]);
const OBJETS_IGNORES = new Set(['console']);
const FONCTIONS_TRADUCTION = new Set(['t']);

function fichiers(racine) {
  const st = statSync(racine);
  if (st.isFile()) return [racine];
  return readdirSync(racine).flatMap((nom) => {
    if (nom === 'node_modules' || nom === '__tests__' || nom === 'i18n') return [];
    const p = path.join(racine, nom);
    if (statSync(p).isDirectory()) return fichiers(p);
    if (!/\.(tsx?|mts)$/.test(nom) || /\.(test|spec)\.tsx?$/.test(nom) || nom.endsWith('.d.ts')) return [];
    return [p];
  });
}

const ressemblePhrase = (s) =>
  /[A-Za-zÀ-ÿ]/.test(s) && (/[À-ÿŒœ’«»…]/.test(s) || /[A-Za-zÀ-ÿ]{2,}\s+[A-Za-zÀ-ÿ]/.test(s));
const ressembleTechnique = (s) =>
  /^(https?:|mailto:|tel:|\/|#|\.|@|data:)/.test(s) ||
  /^[\w.-]+\/[\w./-]+$/.test(s) ||
  /^[a-z0-9_-]+(:[a-z0-9_-]+)*$/.test(s) ||
  /^[a-z][\w-]*(\s+[a-z!][\w:/[\]().%-]*)+$/.test(s); // classes Tailwind

function nomAppel(expr) {
  if (ts.isIdentifier(expr)) return expr.text;
  if (ts.isPropertyAccessExpression(expr)) return expr.name.text;
  return undefined;
}
function objetAppel(expr) {
  if (ts.isPropertyAccessExpression(expr) && ts.isIdentifier(expr.expression)) return expr.expression.text;
  return undefined;
}

function ignore(node) {
  for (let p = node.parent, enfant = node; p; enfant = p, p = p.parent) {
    if (ts.isImportDeclaration(p) || ts.isExportDeclaration(p) || ts.isImportTypeNode?.(p)) return true;
    if (ts.isLiteralTypeNode(p) || ts.isTypeNode(p)) return true;
    if (ts.isPropertyAssignment(p) && p.name === enfant) return true;
    if (ts.isJsxAttribute(p)) {
      const nom = p.name.getText();
      if (nom === 'className' || nom === 'i18nKey' || nom === 'ns' || nom === 'key' ||
          nom.startsWith('data-') || nom === 'id' || nom === 'htmlFor' || nom === 'to' ||
          nom === 'href' || nom === 'src' || nom === 'type' || nom === 'name' || nom === 'value' ||
          nom === 'variant' || nom === 'size' || nom === 'side' || nom === 'align' || nom === 'role') return true;
    }
    if (ts.isCallExpression(p) || ts.isNewExpression(p)) {
      const nom = p.expression && nomAppel(p.expression);
      const objet = p.expression && objetAppel(p.expression);
      if (nom && APPELS_IGNORES.has(nom)) return true;
      if (objet && OBJETS_IGNORES.has(objet)) return true;
      if (nom && FONCTIONS_TRADUCTION.has(nom) && p.arguments[0] === enfant) return true;
    }
    if (ts.isElementAccessExpression(p) && p.argumentExpression === enfant) return true;
    if (ts.isBinaryExpression(p) && /===|!==|==|!=/.test(p.operatorToken.getText())) return true;
    if (ts.isCaseClause(p) && p.expression === enfant) return true;
  }
  return false;
}

let total = 0;
for (const racine of racines) {
  for (const fichier of fichiers(racine)) {
    const source = ts.createSourceFile(fichier, readFileSync(fichier, 'utf8'), ts.ScriptTarget.Latest, true,
      fichier.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
    const trouves = [];
    const signaler = (node, texte) => {
      const { line } = source.getLineAndCharacterOfPosition(node.getStart());
      trouves.push(`${fichier}:${line + 1}: ${texte.replace(/\s+/g, ' ').trim().slice(0, 100)}`);
    };
    const visiter = (node) => {
      if (ts.isJsxText(node)) {
        const texte = node.getText();
        if (/[A-Za-zÀ-ÿ]/.test(texte)) signaler(node, texte);
      } else if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
        const texte = node.text;
        const attribut = node.parent && ts.isJsxAttribute(node.parent) ? node.parent.name.getText() : undefined;
        if (!ignore(node) && !ressembleTechnique(texte) &&
            ((attribut && ATTRIBUTS_LISIBLES.has(attribut) && /[A-Za-zÀ-ÿ]/.test(texte)) || ressemblePhrase(texte))) {
          signaler(node, texte);
        }
      } else if (ts.isTemplateExpression(node)) {
        const texte = [node.head.text, ...node.templateSpans.map((s) => s.literal.text)].join('…');
        if (!ignore(node) && !ressembleTechnique(texte) && ressemblePhrase(texte)) signaler(node, texte);
      }
      ts.forEachChild(node, visiter);
    };
    visiter(source);
    total += trouves.length;
    if (compte) {
      if (trouves.length) console.log(`${String(trouves.length).padStart(4)}  ${fichier}`);
    } else {
      trouves.forEach((l) => console.log(l));
    }
  }
}
console.error(`${total} texte(s) candidat(s)`);
