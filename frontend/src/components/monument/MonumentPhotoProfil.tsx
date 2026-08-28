import { useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { IconModifier, IconSupprimer } from '@/components/icons';
import { Clover } from '@/components/illustrations';
import { PhotoCropDialog } from '@/components/monument/PhotoCropDialog';
import { monumentPhotoProfil } from '@/lib/monument-photo';
import { monumentService } from '@/services/monument.service';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useAuthStore } from '@/stores/useAuthStore';
import { C } from '@/lib/brand';
import type { Monument } from '@/types';

/** 5 Mo : au-delà, c'est une photo brute d'appareil, inutile pour une vignette. */
const TAILLE_MAX = 5 * 1024 * 1024;

/** Format du cadre, aligné sur le héros du tableau de bord (cf. PhotoCropDialog). */
const RATIO = 9 / 16;

interface MonumentPhotoProfilProps {
  monument: Monument;
  /** Co-chef de projet ou plus : seul lui peut changer la photo. */
  canEdit: boolean;
  /** Largeur du cadre 16:9, en pixels ; la hauteur s'en déduit. */
  width?: number;
}

/**
 * Photo de profil du monument, à côté de son nom : le portrait du BIEN, celui
 * qu'on retrouve sur les cartes de « Mes monuments » et sur le tableau de bord.
 *
 * Sans photo, la fleur Monumia sur bleu profond tient le cadre. Un clic ouvre
 * le recadrage quand une photo est déjà là, le sélecteur de fichier sinon —
 * toute photo passe par le cadre de recadrage avant d'être envoyée.
 */
export function MonumentPhotoProfil({
  monument,
  canEdit,
  width = 148,
}: MonumentPhotoProfilProps) {
  const height = Math.round(width * RATIO);
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  // Ce qu'on est en train de recadrer : un fichier tout juste choisi, ou l'URL
  // signée de la photo en place. `null` = pas de recadrage ouvert.
  const [aRecadrer, setARecadrer] = useState<File | string | null>(null);
  const updateMonument = useMonumentStore((s) => s.updateMonument);
  const userId = useAuthStore((s) => s.user?.id);

  const photo = monumentPhotoProfil(monument);
  const url = photo?.signedUrl ?? null;

  function handleFile(file: File | undefined) {
    if (inputRef.current) inputRef.current.value = '';
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error('Choisissez une image (JPEG, PNG…).');
      return;
    }
    if (file.size > TAILLE_MAX) {
      toast.error('Image trop lourde : 5 Mo maximum.');
      return;
    }
    setARecadrer(file);
  }

  async function handleCropped(file: File) {
    if (!userId) {
      toast.error('Session expirée, reconnectez-vous.');
      return;
    }
    setBusy(true);
    try {
      const nouvelle = await monumentService.setPhotoProfil(monument.id, file, userId);
      // La photo de profil est unique : elle remplace l'ancienne dans le tableau.
      updateMonument(monument.id, {
        photos: [nouvelle, ...monument.photos.filter((p) => p.type !== 'profil')],
      });
      setARecadrer(null);
      toast.success('Photo mise à jour.');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Impossible d'enregistrer la photo.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove() {
    setBusy(true);
    try {
      await monumentService.removePhotoProfil(monument.id);
      updateMonument(monument.id, {
        photos: monument.photos.filter((p) => p.type !== 'profil'),
      });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Impossible de retirer la photo.');
    } finally {
      setBusy(false);
    }
  }

  // Une photo héritée (façade, ancien dépôt) s'affiche mais ne se retire pas
  // ici : elle appartient à la galerie de la fiche.
  const removable = canEdit && photo?.type === 'profil';

  return (
    <div className="group/photo flex shrink-0 flex-col items-center gap-1" style={{ width }}>
      <div className="relative" style={{ width, height }}>
        <div
          className="h-full w-full overflow-hidden rounded-2xl"
          style={{
            background: url ? undefined : `linear-gradient(150deg, ${C.blue}, ${C.blueDark})`,
            boxShadow: 'inset 0 0 0 1px rgba(7,42,114,0.08)',
          }}
        >
          {url ? (
            <img
              src={url}
              alt={`Photo du monument ${monument.nom}`}
              className="h-full w-full object-cover"
            />
          ) : (
            <span className="flex h-full w-full items-center justify-center">
              <Clover size={height * 0.52} className="text-white" style={{ opacity: 0.9 }} />
            </span>
          )}
        </div>

        {canEdit && (
          <>
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              className="sr-only"
              onChange={(e) => handleFile(e.target.files?.[0])}
            />
            <button
              type="button"
              onClick={() => (url ? setARecadrer(url) : inputRef.current?.click())}
              disabled={busy}
              aria-label={url ? 'Recadrer la photo du monument' : 'Ajouter une photo du monument'}
              className="absolute inset-0 flex items-center justify-center rounded-2xl text-white opacity-0 transition-opacity duration-200 hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-wait disabled:opacity-100"
              style={{ background: 'rgba(7,42,114,0.62)' }}
            >
              {busy ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <IconModifier className="h-5 w-5" strokeWidth={2} />
              )}
            </button>
            {removable && !busy && (
              <button
                type="button"
                onClick={handleRemove}
                aria-label="Retirer la photo du monument"
                /* Discrète au repos : elle n'apparaît qu'au survol de la
                   vignette, ou quand elle prend le focus au clavier — sans quoi
                   elle serait inatteignable sans souris. */
                className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full border text-white opacity-0 shadow-sm transition-all hover:scale-105 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-hover/photo:opacity-100"
                style={{ background: C.blue, borderColor: C.card }}
              >
                <IconSupprimer className="h-3 w-3" strokeWidth={2} />
              </button>
            )}
          </>
        )}
      </div>

      {/* L'invite discrète sous la vignette : sans elle, rien ne dit qu'elle se
          clique — la pastille de survol n'existe pas au doigt. */}
      {canEdit && (
        <button
          type="button"
          onClick={() => (url ? setARecadrer(url) : inputRef.current?.click())}
          disabled={busy}
          className="inline-flex items-center gap-1 text-[11px] font-medium transition-colors hover:underline disabled:cursor-wait"
          style={{ color: C.grayMuted }}
        >
          <IconModifier className="h-3 w-3" strokeWidth={2} aria-hidden />
          {url ? 'Modifier' : 'Ajouter'}
        </button>
      )}

      <PhotoCropDialog
        open={aRecadrer !== null}
        onOpenChange={(o) => {
          if (!o && !busy) setARecadrer(null);
        }}
        source={aRecadrer}
        busy={busy}
        onCropped={handleCropped}
        onChooseAnother={() => inputRef.current?.click()}
      />
    </div>
  );
}
