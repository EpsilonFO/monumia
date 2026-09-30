import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { IconRecherche } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { adminService } from '@/services/admin.service';
import { filtrerAides } from '@/lib/admin-catalogue';
import { C, SERIF } from '@/lib/brand';
import type { AdminAide } from '@/types/admin.types';

interface Props {
  onErreur: (err: unknown, repli: string) => void;
}

/**
 * Le catalogue, et le geste de retrait.
 *
 * Une aide retirée disparaît des diagnostics, sa fiche répond 404 et on ne peut
 * plus ouvrir de dossier dessus — y compris pour qui la suivait déjà. C'est
 * pour cela que le motif compte : l'autre fondateur doit pouvoir comprendre la
 * décision six mois plus tard.
 */
export function AdminAidesPanel({ onErreur }: Props) {
  const [aides, setAides] = useState<AdminAide[]>([]);
  const [chargement, setChargement] = useState(true);
  const [recherche, setRecherche] = useState('');
  const [slugOuvert, setSlugOuvert] = useState<string | null>(null);
  const [retiree, setRetiree] = useState(false);
  const [motif, setMotif] = useState('');
  const [enregistrement, setEnregistrement] = useState(false);

  useEffect(() => {
    let annule = false;
    adminService
      .listAides()
      .then((lignes) => {
        if (!annule) setAides(lignes);
      })
      .catch((err) => onErreur(err, 'Catalogue indisponible'))
      .finally(() => {
        if (!annule) setChargement(false);
      });
    return () => {
      annule = true;
    };
  }, [onErreur]);

  const visibles = useMemo(() => filtrerAides(aides, recherche), [aides, recherche]);
  const nbRetirees = useMemo(() => aides.filter((a) => a.retiree).length, [aides]);
  const ouverte = aides.find((a) => a.slug === slugOuvert) ?? null;

  const ouvrir = (aide: AdminAide) => {
    setSlugOuvert(aide.slug);
    setRetiree(aide.retiree);
    setMotif(aide.motif ?? '');
  };

  const enregistrer = async () => {
    if (!ouverte) return;
    setEnregistrement(true);
    try {
      const ligne = retiree
        ? await adminService.retirerAide(ouverte.slug, motif)
        : await adminService.republierAide(ouverte.slug);
      // On remplace la ligne avec la réponse plutôt que de relister : c'est la
      // même forme, et le serveur y met l'état qu'il vient d'enregistrer.
      setAides((lignes) => lignes.map((l) => (l.slug === ligne.slug ? ligne : l)));
      setMotif(ligne.motif ?? '');
      toast.success(ligne.retiree ? 'Aide retirée du catalogue' : 'Aide republiée');
    } catch (err) {
      onErreur(err, 'Enregistrement impossible');
    } finally {
      setEnregistrement(false);
    }
  };

  const modifie = ouverte ? retiree !== ouverte.retiree || motif !== (ouverte.motif ?? '') : false;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 sm:max-w-md">
          <IconRecherche
            className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
            strokeWidth={1.8}
          />
          <Input
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
            placeholder="Rechercher une aide (nom, organisme, slug)…"
            className="h-10 pl-9 text-[16px]"
          />
        </div>
        <p className="text-[15px] text-muted-foreground">
          {aides.length} aides · {nbRetirees} retirée{nbRetirees > 1 ? 's' : ''}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_400px]">
        <div className="overflow-hidden rounded-xl border border-border bg-card">
          {chargement ? (
            <p className="px-4 py-8 text-center text-[16px] text-muted-foreground">Chargement…</p>
          ) : visibles.length === 0 ? (
            <p className="px-4 py-8 text-center text-[16px] text-muted-foreground">
              Aucune aide ne correspond à votre recherche.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Aide</TableHead>
                  <TableHead className="hidden md:table-cell">Organisme</TableHead>
                  <TableHead>État</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibles.map((aide) => (
                  <TableRow
                    key={aide.slug}
                    onClick={() => ouvrir(aide)}
                    className={`cursor-pointer ${aide.slug === slugOuvert ? 'bg-secondary' : ''}`}
                  >
                    <TableCell>
                      <p className="font-medium text-foreground">{aide.nom}</p>
                      <p className="font-mono text-[13.5px] text-muted-foreground">{aide.slug}</p>
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-[15px] text-muted-foreground">
                      {aide.organisme}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1.5">
                        {aide.retiree && <Badge variant="destructive">Retirée</Badge>}
                        {aide.disponibilite === 'bientot' && <Badge variant="secondary">Bientôt</Badge>}
                        {!aide.engineReady && <Badge variant="outline">Non typée</Badge>}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>

        <aside className="h-fit rounded-xl border border-border bg-card p-5">
          {!ouverte ? (
            <p className="text-[16px] text-muted-foreground">
              Sélectionnez une aide pour la retirer du catalogue ou la republier.
            </p>
          ) : (
            <div className="space-y-4">
              <div>
                <h2 className="text-[19px]" style={{ fontFamily: SERIF, color: C.ink }}>
                  {ouverte.nom}
                </h2>
                <p className="font-mono text-[13.5px] text-muted-foreground">{ouverte.slug}</p>
              </div>

              <label className="flex items-start gap-3">
                <Switch checked={retiree} onCheckedChange={setRetiree} className="mt-0.5" />
                <span className="text-[16px]">
                  <span className="font-medium text-foreground">Retirée du catalogue</span>
                  <span className="block text-[14.5px] text-muted-foreground">
                    L’aide disparaît des diagnostics, sa fiche devient introuvable et aucun dossier
                    ne peut plus être ouvert dessus.
                  </span>
                </span>
              </label>

              <div className="space-y-1.5">
                <label htmlFor="motif-retrait" className="text-[15px] font-medium text-foreground">
                  Motif
                </label>
                <Textarea
                  id="motif-retrait"
                  value={motif}
                  onChange={(e) => setMotif(e.target.value)}
                  disabled={!retiree}
                  rows={3}
                  maxLength={500}
                  placeholder="Dispositif supprimé par la région, doublon de…"
                  className="text-[16px]"
                />
                {ouverte.retiree && ouverte.retireeLe && (
                  <p className="text-[14px] text-muted-foreground">
                    Retirée le {new Date(ouverte.retireeLe).toLocaleDateString('fr-FR')}
                  </p>
                )}
              </div>

              <button
                onClick={enregistrer}
                disabled={enregistrement || !modifie}
                className="inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-[16px] font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                style={{ background: C.blue }}
              >
                {enregistrement ? 'Enregistrement…' : 'Enregistrer'}
              </button>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
