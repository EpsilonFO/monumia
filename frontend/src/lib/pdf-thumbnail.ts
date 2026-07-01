import * as pdfjsLib from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrl;

// Cache par chemin de stockage (l'URL signée change à chaque appel, pas le path).
const cache = new Map<string, string>();

function cacheKey(signedUrl: string): string {
  try { return new URL(signedUrl).pathname; } catch { return signedUrl; }
}

/**
 * Rend la 1re page d'un PDF en miniature (dataURL JPEG) pour l'aperçu des cartes.
 * pdfjs est chargé à la demande (ce module n'est importé que via `import()`),
 * et le résultat est mémoïsé par chemin de fichier. Renvoie `null` si le rendu
 * échoue → la carte retombe alors sur le bandeau coloré.
 *
 * Notes v6 :
 *  • on passe `canvas` (recommandé) et non `canvasContext` (legacy) ;
 *  • `disableRange/Stream/AutoFetch` : on télécharge le PDF en un seul GET (comme
 *    une image) au lieu de requêtes Range, souvent bloquées par le CORS Supabase.
 */
export async function renderPdfThumbnail(signedUrl: string): Promise<string | null> {
  const key = cacheKey(signedUrl);
  const cached = cache.get(key);
  if (cached) return cached;

  const loadingTask = pdfjsLib.getDocument({
    url: signedUrl,
    disableRange: true,
    disableStream: true,
    disableAutoFetch: true,
  });
  try {
    const pdf = await loadingTask.promise;
    const page = await pdf.getPage(1);

    const base = page.getViewport({ scale: 1 });
    const scale = Math.min(2, 480 / base.width);
    const viewport = page.getViewport({ scale });

    const canvas = document.createElement('canvas');
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);

    await page.render({ canvas, viewport }).promise;
    const dataUrl = canvas.toDataURL('image/jpeg', 0.72);
    cache.set(key, dataUrl);
    return dataUrl;
  } catch (e) {
    console.warn('[pdf-thumbnail] échec du rendu de la 1re page', e);
    return null;
  } finally {
    // Libération best-effort des ressources (worker + document) — non bloquant.
    try { await loadingTask.destroy(); } catch { /* ignoré */ }
  }
}
