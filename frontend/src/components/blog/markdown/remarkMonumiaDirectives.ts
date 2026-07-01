import { visit } from 'unist-util-visit';

// Types structurels minimalistes (évite de dépendre des typings mdast/hast).
/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyNode = any;

const CALLOUT_NAMES = new Set(['remarque', 'attention', 'astuce', 'exemple']);

/** Concatène le texte de tous les descendants d'un nœud mdast. */
function nodeText(node: AnyNode): string {
  if (!node) return '';
  if (typeof node.value === 'string') return node.value;
  if (Array.isArray(node.children)) return node.children.map(nodeText).join('');
  return '';
}

/** Texte du premier nœud `strong` rencontré dans un sous-arbre. */
function firstStrongText(node: AnyNode): string {
  let found = '';
  visit(node, 'strong', (n: AnyNode) => {
    if (!found) found = nodeText(n).trim();
  });
  return found;
}

/** Retire les séparateurs de tête (tirets, em-dash, deux-points, espaces). */
function stripLead(s: string): string {
  return s.replace(/^[\s—–\-:]+/, '').trim();
}

/** Si le 1er enfant est le label de directive, le retire et renvoie son texte. */
function takeLabel(node: AnyNode): string {
  const kids: AnyNode[] = node.children ?? [];
  if (kids[0]?.data?.directiveLabel) {
    node.children = kids.slice(1);
    return nodeText(kids[0]).trim();
  }
  return '';
}

function firstList(node: AnyNode): AnyNode | undefined {
  return (node.children ?? []).find((c: AnyNode) => c.type === 'list');
}

function setData(node: AnyNode, hName: string, hProperties: Record<string, unknown>) {
  node.data = node.data || {};
  node.data.hName = hName;
  node.data.hProperties = hProperties;
}

export default function remarkMonumiaDirectives() {
  return (tree: AnyNode) => {
    visit(tree, (node: AnyNode) => {
      if (node.type !== 'containerDirective' && node.type !== 'leafDirective') {
        return;
      }
      const name: string = node.name ?? '';

      if (CALLOUT_NAMES.has(name)) {
        const title = takeLabel(node);
        setData(node, 'mon-callout', { variant: name, title });
        return;
      }

      if (name === 'figure') {
        const caption = takeLabel(node);
        setData(node, 'mon-figure', { caption });
        return;
      }

      if (name === 'chiffres') {
        const items = (firstList(node)?.children ?? []).map((item: AnyNode) => {
          const full = nodeText(item).trim();
          const value = firstStrongText(item);
          const label = value && full.startsWith(value) ? full.slice(value.length) : full;
          return { value, label: stripLead(label) };
        });
        node.children = [];
        setData(node, 'mon-keyfigures', {
          data: JSON.stringify(items),
          display: (node.attributes?.display as string) || 'cartes',
        });
        return;
      }

      if (name === 'barres') {
        const items: Array<{ label: string; value: number }> = [];
        for (const item of firstList(node)?.children ?? []) {
          const m = nodeText(item).trim().match(/^(.*?):\s*([\d.,]+)\s*$/);
          if (m) items.push({ label: m[1].trim(), value: Number(m[2].replace(',', '.')) });
        }
        const unit = (node.attributes?.unit as string) || '%';
        node.children = [];
        setData(node, 'mon-barchart', { data: JSON.stringify(items), unit });
        return;
      }

      if (name === 'comparatif') {
        const rows = (firstList(node)?.children ?? []).map((item: AnyNode) => {
          const parts = nodeText(item)
            .split('|')
            .map((s: string) => s.trim());
          return { aspect: parts[0] ?? '', a: parts[1] ?? '', b: parts[2] ?? '' };
        });
        const cola = (node.attributes?.a as string) || '';
        const colb = (node.attributes?.b as string) || '';
        node.children = [];
        setData(node, 'mon-comparison', {
          data: JSON.stringify(rows),
          cola,
          colb,
          display: (node.attributes?.display as string) || 'tableau',
        });
        return;
      }

      if (name === 'etapes') {
        const steps = (firstList(node)?.children ?? []).map((item: AnyNode) => {
          const full = nodeText(item).trim();
          const title = firstStrongText(item);
          const description = title && full.startsWith(title) ? full.slice(title.length) : full;
          return { title, description: stripLead(description) };
        });
        node.children = [];
        setData(node, 'mon-steps', {
          data: JSON.stringify(steps),
          display: (node.attributes?.display as string) || 'frise',
        });
        return;
      }

      if (name === 'frise') {
        const items = (firstList(node)?.children ?? []).map((item: AnyNode) => {
          const full = nodeText(item).trim();
          const date = firstStrongText(item);
          const event = date && full.startsWith(date) ? full.slice(date.length) : full;
          return { date, event: stripLead(event) };
        });
        node.children = [];
        setData(node, 'mon-timeline', { data: JSON.stringify(items) });
        return;
      }

      if (name === 'decision') {
        const title = takeLabel(node);
        const branches = (firstList(node)?.children ?? []).map((item: AnyNode) => {
          const parts = nodeText(item)
            .split('|')
            .map((s: string) => s.trim());
          let yes = '';
          let no = '';
          for (const p of parts.slice(1)) {
            const m = p.match(/^(oui|non)\s*:\s*(.*)$/i);
            if (m) {
              if (/^oui$/i.test(m[1])) yes = m[2].trim();
              else no = m[2].trim();
            }
          }
          return { q: parts[0] ?? '', yes, no };
        });
        node.children = [];
        setData(node, 'mon-decision', { data: JSON.stringify(branches), title });
        return;
      }

      if (name === 'citation') {
        const source = takeLabel(node);
        setData(node, 'mon-quote', { source });
        return;
      }

      if (name === 'checklist') {
        const title = takeLabel(node);
        const items = (firstList(node)?.children ?? []).map((item: AnyNode) =>
          nodeText(item).trim(),
        );
        node.children = [];
        setData(node, 'mon-checklist', { data: JSON.stringify(items), title });
        return;
      }

      if (name === 'cout') {
        const items: Array<{ label: string; value: number }> = [];
        for (const item of firstList(node)?.children ?? []) {
          const m = nodeText(item)
            .trim()
            .match(/^(.*?):\s*([\d\s.,]+)\s*$/);
          if (m) {
            items.push({
              label: m[1].trim(),
              value: Number(m[2].replace(/\s/g, '').replace(',', '.')),
            });
          }
        }
        const unit = (node.attributes?.unit as string) || '€';
        node.children = [];
        setData(node, 'mon-cost', { data: JSON.stringify(items), unit });
        return;
      }

      if (name === 'exergue') {
        const value = takeLabel(node);
        setData(node, 'mon-pullstat', { value });
        return;
      }
    });
  };
}
