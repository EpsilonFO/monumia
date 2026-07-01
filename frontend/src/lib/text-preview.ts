import { unzipSync, strFromU8 } from 'fflate';

const MAX_CHARS = 700;
const MAX_ROWS = 7;
const MAX_COLS = 5;

export type PreviewData =
  | { kind: 'text'; text: string }
  | { kind: 'grid'; rows: string[][] }
  | null;

export type TextSource = 'txt' | 'docx' | 'csv' | 'xlsx';

function decodeEntities(s: string): string {
  return s
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n));
}

function cleanText(raw: string): string {
  return raw
    .replace(/\r/g, '')
    .split('\n').map((l) => l.replace(/\s+$/g, ''))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
    .slice(0, MAX_CHARS);
}

function csvToRows(raw: string): string[][] {
  return raw.replace(/\r/g, '').split('\n').filter((l) => l.trim())
    .slice(0, MAX_ROWS)
    .map((line) => line.split(/[,;\t]/).slice(0, MAX_COLS).map((c) => c.replace(/^"|"$/g, '').trim()));
}

async function unzipEntry(signedUrl: string, name: string): Promise<string | null> {
  const buf = new Uint8Array(await (await fetch(signedUrl)).arrayBuffer());
  const files = unzipSync(buf, { filter: (f) => f.name === name });
  return files[name] ? strFromU8(files[name]) : null;
}

/**
 * Aperçu d'un document texte/bureautique : texte enroulé (TXT, DOCX) ou petit
 * tableau (CSV, XLSX). `fflate` (dézip) n'est chargé qu'avec ce module, lui-même
 * importé à la demande. Renvoie `null` si rien d'exploitable.
 */
export async function extractPreview(signedUrl: string, source: TextSource): Promise<PreviewData> {
  if (source === 'txt') {
    const text = cleanText(await (await fetch(signedUrl)).text());
    return text ? { kind: 'text', text } : null;
  }

  if (source === 'csv') {
    const rows = csvToRows(await (await fetch(signedUrl)).text());
    return rows.length ? { kind: 'grid', rows } : null;
  }

  if (source === 'docx') {
    const xml = await unzipEntry(signedUrl, 'word/document.xml');
    if (!xml) return null;
    const text = cleanText(decodeEntities(
      xml.replace(/<\/w:p>/g, '\n').replace(/<[^>]+>/g, ''),
    ));
    return text ? { kind: 'text', text } : null;
  }

  // xlsx : shared strings + 1re feuille → petit tableau
  const shared = await unzipEntry(signedUrl, 'xl/sharedStrings.xml');
  const sheet = await unzipEntry(signedUrl, 'xl/worksheets/sheet1.xml');
  if (!sheet) return null;
  const strings = shared
    ? [...shared.matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((m) => decodeEntities(m[1]))
    : [];
  const rows: string[][] = [];
  for (const rowM of [...sheet.matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/g)].slice(0, MAX_ROWS)) {
    const cells: string[] = [];
    for (const cM of [...rowM[1].matchAll(/<c\b([^>]*)>([\s\S]*?)<\/c>/g)].slice(0, MAX_COLS)) {
      const attrs = cM[1];
      const inner = cM[2];
      const inline = inner.match(/<t[^>]*>([\s\S]*?)<\/t>/);
      const v = inner.match(/<v>([\s\S]*?)<\/v>/);
      let val = '';
      if (inline) val = decodeEntities(inline[1]);
      else if (v) val = /t="s"/.test(attrs) ? (strings[+v[1]] ?? '') : v[1];
      cells.push(val);
    }
    if (cells.length) rows.push(cells);
  }
  return rows.length ? { kind: 'grid', rows } : null;
}
