import { documentService } from '@/services/document.service';

/**
 * Télécharge un document via son URL signée (bucket privé) puis déclenche
 * l'enregistrement du fichier côté navigateur. Mutualisé entre l'aperçu et les
 * cartes de document pour un comportement identique partout.
 */
export async function downloadDocument(doc: { id: string; nomFichier: string }): Promise<void> {
  const url = await documentService.getSignedUrl(doc.id);
  const res = await fetch(url);
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const a = Object.assign(window.document.createElement('a'), { href: blobUrl, download: doc.nomFichier });
  window.document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(blobUrl);
}
