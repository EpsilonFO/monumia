import { useEffect } from 'react';

/** Met à jour le <title> et la meta description le temps que la page est montée. */
export function useDocumentMeta(title: string, description?: string) {
  useEffect(() => {
    const prevTitle = document.title;
    document.title = title;

    let metaEl: HTMLMetaElement | null = null;
    let created = false;
    let prevContent: string | null = null;
    if (description) {
      metaEl = document.querySelector('meta[name="description"]');
      if (!metaEl) {
        metaEl = document.createElement('meta');
        metaEl.setAttribute('name', 'description');
        document.head.appendChild(metaEl);
        created = true;
      }
      prevContent = metaEl.getAttribute('content');
      metaEl.setAttribute('content', description);
    }

    return () => {
      document.title = prevTitle;
      if (metaEl) {
        if (created) metaEl.remove();
        else if (prevContent !== null) metaEl.setAttribute('content', prevContent);
      }
    };
  }, [title, description]);
}
