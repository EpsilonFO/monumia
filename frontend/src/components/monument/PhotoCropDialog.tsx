import { useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { C } from '@/lib/brand';

/**
 * Cadre de recadrage, en pixels CSS. Format 16:9 : c'est celui du héros du
 * tableau de bord, et la photo de profil sert les deux — un carré aurait été
 * retaillé une seconde fois à l'affichage, hors du contrôle de l'utilisateur.
 */
const VUE_L = 320;
const VUE_H = 180;
/** Image produite : large pour le héros, légère pour les vignettes. */
const SORTIE_L = 1280;
const SORTIE_H = 720;
const ZOOM_MAX = 4;

/** Ce qu'on recadre : un fichier fraîchement choisi, ou une URL signée. */
export type CropSource = File | string;

interface PhotoCropDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  source: CropSource | null;
  /** Enregistrement en cours côté appelant. */
  busy?: boolean;
  onCropped: (file: File) => void | Promise<void>;
  /** Proposé dans le pied du dialogue quand une autre photo peut remplacer celle-ci. */
  onChooseAnother?: () => void;
}

/** Identité de la source : changer de photo remonte le recadreur à neuf. */
function sourceKey(source: CropSource): string {
  return typeof source === 'string' ? source : `${source.name}:${source.size}:${source.lastModified}`;
}

/**
 * Recadrage 16:9 d'une photo : on déplace l'image à la souris (ou au doigt) et
 * on ajuste le zoom, le cadre visible étant exactement ce qui sera enregistré.
 *
 * Fait maison plutôt qu'une dépendance de plus : le besoin tient en une image
 * translatée dans un cadre, puis un `drawImage` de la zone visible.
 */
export function PhotoCropDialog({
  open,
  onOpenChange,
  source,
  busy = false,
  onCropped,
  onChooseAnother,
}: PhotoCropDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Recadrer la photo</DialogTitle>
          <DialogDescription>
            Déplacez l&rsquo;image et ajustez le zoom : ce que montre le cadre sera la photo du
            monument.
          </DialogDescription>
        </DialogHeader>
        {source && (
          <Recadreur
            key={sourceKey(source)}
            source={source}
            busy={busy}
            onCropped={onCropped}
            onChooseAnother={onChooseAnother}
            onCancel={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

interface RecadreurProps {
  source: CropSource;
  busy: boolean;
  onCropped: (file: File) => void | Promise<void>;
  onChooseAnother?: () => void;
  onCancel: () => void;
}

/** Le cadre lui-même. Remonté à chaque nouvelle source, d'où l'état tout neuf. */
function Recadreur({ source, busy, onCropped, onChooseAnother, onCancel }: RecadreurProps) {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  // Une URL passe par fetch → blob : le lien signé vient d'un autre domaine, et
  // un <img> cross-origin condamnerait le canvas (`toBlob` refuserait de rendre).
  useEffect(() => {
    let annule = false;
    let objectUrl: string | null = null;

    (async () => {
      const blob = typeof source === 'string' ? await (await fetch(source)).blob() : source;
      objectUrl = URL.createObjectURL(blob);
      const img = new Image();
      img.src = objectUrl;
      await img.decode();
      if (!annule) setImage(img);
    })().catch(() => {
      if (!annule) setErreur("Impossible de charger l'image.");
    });

    return () => {
      annule = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [source]);

  // Échelle « cover » : au zoom 1, l'image remplit tout juste le cadre.
  const base = image
    ? Math.max(VUE_L / image.naturalWidth, VUE_H / image.naturalHeight)
    : 1;
  const echelle = base * zoom;
  const largeur = image ? image.naturalWidth * echelle : 0;
  const hauteur = image ? image.naturalHeight * echelle : 0;

  /** Le cadre ne doit jamais laisser voir le vide : on borne le déplacement. */
  function borner(x: number, y: number) {
    const maxX = Math.max(0, (largeur - VUE_L) / 2);
    const maxY = Math.max(0, (hauteur - VUE_H) / 2);
    return { x: Math.min(maxX, Math.max(-maxX, x)), y: Math.min(maxY, Math.max(-maxY, y)) };
  }

  // Borné au rendu, et non dans un effet : dézoomer recentre aussitôt, sans
  // repasser par un état intermédiaire qui laisserait voir un bord vide.
  const vue = borner(offset.x, offset.y);

  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if (!image) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, ox: vue.x, oy: vue.y };
  }

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const d = drag.current;
    if (!d) return;
    setOffset(borner(d.ox + (e.clientX - d.x), d.oy + (e.clientY - d.y)));
  }

  function onPointerUp() {
    drag.current = null;
  }

  async function handleValider() {
    if (!image) return;
    const canvas = document.createElement('canvas');
    canvas.width = SORTIE_L;
    canvas.height = SORTIE_H;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Coin haut-gauche de l'image dans le repère du cadre, puis conversion de
    // la fenêtre visible en coordonnées de l'image d'origine.
    const left = (VUE_L - largeur) / 2 + vue.x;
    const top = (VUE_H - hauteur) / 2 + vue.y;
    ctx.drawImage(
      image,
      -left / echelle,
      -top / echelle,
      VUE_L / echelle,
      VUE_H / echelle,
      0,
      0,
      SORTIE_L,
      SORTIE_H,
    );

    const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, 'image/jpeg', 0.9));
    if (!blob) {
      setErreur("Impossible de produire l'image recadrée.");
      return;
    }
    await onCropped(new File([blob], 'photo-profil.jpg', { type: 'image/jpeg' }));
  }

  return (
    <>
      <div className="flex flex-col items-center gap-4">
        <div
          className="relative touch-none select-none overflow-hidden rounded-2xl"
          style={{
            width: VUE_L,
            height: VUE_H,
            maxWidth: '100%',
            background: C.cream,
            cursor: image ? 'grab' : 'default',
            boxShadow: 'inset 0 0 0 1px rgba(7,42,114,0.10)',
          }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          {image ? (
            <img
              src={image.src}
              alt=""
              draggable={false}
              className="absolute left-1/2 top-1/2 max-w-none"
              style={{
                width: largeur,
                height: hauteur,
                transform: `translate(calc(-50% + ${vue.x}px), calc(-50% + ${vue.y}px))`,
              }}
            />
          ) : (
            <span className="flex h-full w-full items-center justify-center text-[15px] text-muted-foreground">
              {erreur ?? <Loader2 className="h-5 w-5 animate-spin" />}
            </span>
          )}
        </div>

        <label className="flex w-full items-center gap-3" style={{ maxWidth: VUE_L }}>
          <span className="text-[14.5px]" style={{ color: C.grayFg }}>
            Zoom
          </span>
          <input
            type="range"
            min={1}
            max={ZOOM_MAX}
            step={0.01}
            value={zoom}
            disabled={!image}
            onChange={(e) => setZoom(Number(e.target.value))}
            className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full disabled:cursor-not-allowed"
            style={{ accentColor: C.orange, background: C.border }}
          />
        </label>
      </div>

      <DialogFooter className="sm:justify-between">
        {onChooseAnother ? (
          <Button type="button" variant="ghost" onClick={onChooseAnother} disabled={busy}>
            Choisir une autre photo
          </Button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={onCancel} disabled={busy}>
            Annuler
          </Button>
          <Button
            type="button"
            onClick={handleValider}
            disabled={!image || busy}
            style={{ background: C.orange }}
          >
            {busy && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
            Enregistrer
          </Button>
        </div>
      </DialogFooter>
    </>
  );
}
