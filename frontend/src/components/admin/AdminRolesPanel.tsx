import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { IconRecherche } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { adminService } from '@/services/admin.service';
import { useAuthStore } from '@/stores/useAuthStore';
import { filtrerUtilisateurs } from '@/lib/admin-catalogue';
import { C } from '@/lib/brand';
import {
  LIBELLE_ROLE,
  type EtatRole,
  type RoleCompte,
  type UtilisateurAdmin,
} from '@/types/admin.types';

interface Props {
  onErreur: (err: unknown, repli: string) => void;
}

/**
 * Les deux bascules, dans l'ordre des colonnes. La couleur dit laquelle :
 * l'orange de l'accent pour le bêta-test, le bleu institutionnel pour
 * l'administration — la plus lourde des deux.
 */
const BASCULES: { role: RoleCompte; teinte: string; ouvre: string }[] = [
  { role: 'beta_testeur', teinte: C.orangeVif, ouvre: 'l’offre Multi-monuments, sans facturation' },
  { role: 'admin', teinte: C.blue, ouvre: 'cette page, plus l’offre Multi-monuments' },
];

/** Le nom affiché : celui du compte, à défaut son email, à défaut son UUID. */
function intitule(compte: UtilisateurAdmin): string {
  const nom = [compte.prenom, compte.nom].filter(Boolean).join(' ').trim();
  return nom || compte.email || compte.userId;
}

function Bascule({
  etat,
  role,
  teinte,
  enCours,
  onClick,
}: {
  etat: EtatRole;
  role: RoleCompte;
  teinte: string;
  enCours: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!etat.modifiable || enCours}
      // `raison` vient du serveur et dit POURQUOI c'est bloqué : un bouton
      // grisé sans explication est une impasse.
      title={etat.raison ?? undefined}
      aria-pressed={etat.actif}
      className="w-36 shrink-0 rounded-lg border px-3 py-1.5 text-[13px] font-medium transition-all disabled:cursor-not-allowed disabled:opacity-45"
      style={
        etat.actif
          ? { background: teinte, borderColor: teinte, color: '#fff' }
          : { borderColor: C.border, color: C.grayFg }
      }
    >
      {enCours ? '…' : LIBELLE_ROLE[role]}
    </button>
  );
}

/**
 * Les rôles de COMPTE : qui administre le catalogue, qui teste le produit.
 *
 * À ne pas confondre avec les rôles d'ÉQUIPE (co_owner / member), qui portent
 * sur un monument ou un chantier et se gèrent depuis l'onglet Équipe.
 *
 * On part de la LISTE DES COMPTES et on bascule sur place, plutôt que de taper
 * une adresse : on ne peut pas se tromper de destinataire, et on voit du même
 * coup qui a déjà quoi. Chaque clic écrit tout de suite — il n'y a rien à
 * enregistrer ensuite, et le serveur rend la ligne à jour, qui remplace la
 * sienne.
 *
 * Deux bascules sont volontairement bloquées, et le serveur les refuse en 409
 * même si le bouton était cliquable — toutes deux propres à l'administration :
 * se la retirer à soi-même (le seul geste qui pourrait fermer la page pour de
 * bon), et la retirer à un compte du socle `ADMIN_USER_IDS`, que le `.env`
 * rouvrirait aussitôt. C'est le serveur qui en décide (`roles._verrou`), pas ce
 * composant : `modifiable` et `raison` arrivent avec chaque ligne.
 */
export function AdminRolesPanel({ onErreur }: Props) {
  const moi = useAuthStore((s) => s.user?.id);
  const [utilisateurs, setUtilisateurs] = useState<UtilisateurAdmin[]>([]);
  const [tronquee, setTronquee] = useState(false);
  const [chargement, setChargement] = useState(true);
  const [recherche, setRecherche] = useState('');
  const [enCours, setEnCours] = useState<string | null>(null);

  useEffect(() => {
    let annule = false;
    adminService
      .listUtilisateurs()
      .then((corps) => {
        if (annule) return;
        setUtilisateurs(corps.utilisateurs);
        setTronquee(corps.tronquee);
      })
      .catch((err) => onErreur(err, 'Liste des comptes indisponible'))
      .finally(() => {
        if (!annule) setChargement(false);
      });
    return () => {
      annule = true;
    };
  }, [onErreur]);

  const visibles = useMemo(
    () => filtrerUtilisateurs(utilisateurs, recherche),
    [utilisateurs, recherche],
  );
  const compteurs = useMemo(
    () =>
      BASCULES.map(({ role }) => ({
        role,
        nb: utilisateurs.filter((u) => u.roles[role].actif).length,
      })),
    [utilisateurs],
  );

  const basculer = async (compte: UtilisateurAdmin, role: RoleCompte) => {
    const etat = compte.roles[role];
    const cle = `${compte.userId}:${role}`;
    setEnCours(cle);
    try {
      const ligne = etat.actif
        ? await adminService.retirerRole(compte.userId, role)
        : await adminService.attribuerRole(compte.userId, role);
      // On remplace la ligne avec la réponse plutôt que de relister : c'est la
      // même forme, et le serveur y met l'état qu'il vient d'écrire.
      setUtilisateurs((lignes) =>
        lignes.map((l) => (l.userId === ligne.userId ? ligne : l)),
      );
      const libelle = LIBELLE_ROLE[role].toLowerCase();
      toast.success(
        etat.actif
          ? `${intitule(compte)} n’est plus ${libelle}`
          : `${intitule(compte)} est désormais ${libelle}`,
      );
    } catch (err) {
      onErreur(err, 'Changement impossible');
    } finally {
      setEnCours(null);
    }
  };

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
            placeholder="Rechercher un compte (nom, email)…"
            className="h-10 pl-9 text-[14px]"
          />
        </div>
        <p className="text-[13px] text-muted-foreground">
          {utilisateurs.length} compte{utilisateurs.length > 1 ? 's' : ''}
          {compteurs.map(({ role, nb }) => (
            <span key={role}> · {nb} {LIBELLE_ROLE[role].toLowerCase()}{nb > 1 ? 's' : ''}</span>
          ))}
        </p>
      </div>

      <p className="text-[12.5px] text-muted-foreground">
        Un clic donne ou reprend le rôle immédiatement, il n’y a rien à enregistrer.{' '}
        <span className="font-medium text-foreground">Bêta-testeur</span> ouvre{' '}
        {BASCULES[0].ouvre} ; <span className="font-medium text-foreground">Administrateur</span>{' '}
        ouvre {BASCULES[1].ouvre}.
      </p>

      <div className="overflow-hidden rounded-xl border border-border bg-card">
        {chargement ? (
          <p className="px-4 py-8 text-center text-[14px] text-muted-foreground">Chargement…</p>
        ) : visibles.length === 0 ? (
          <p className="px-4 py-8 text-center text-[14px] text-muted-foreground">
            Aucun compte ne correspond à votre recherche.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Compte</TableHead>
                  <TableHead className="hidden lg:table-cell">Inscrit</TableHead>
                  <TableHead className="text-right">Rôles</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibles.map((compte) => (
                  <TableRow key={compte.userId}>
                    <TableCell>
                      <p className="font-medium text-foreground">
                        {intitule(compte)}
                        {compte.userId === moi && (
                          <span className="ml-2 text-[12px] font-normal text-muted-foreground">
                            (vous)
                          </span>
                        )}
                      </p>
                      <p className="text-[12.5px] text-muted-foreground">
                        {compte.email ?? <span className="font-mono">{compte.userId}</span>}
                      </p>
                      {(compte.compteIntrouvable || compte.roles.admin.source === 'socle') && (
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {compte.roles.admin.source === 'socle' && (
                            <Badge variant="outline" title="Vient de la variable ADMIN_USER_IDS">
                              ADMIN_USER_IDS
                            </Badge>
                          )}
                          {compte.compteIntrouvable && (
                            <Badge variant="destructive">Compte introuvable</Badge>
                          )}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell text-[13px] text-muted-foreground">
                      {compte.createdAt
                        ? new Date(compte.createdAt).toLocaleDateString('fr-FR')
                        : '—'}
                    </TableCell>
                    <TableCell>
                      {/* `justify-end` + largeur fixe : les bascules s'alignent
                          d'une ligne à l'autre, on lit la colonne d'un coup. */}
                      <div className="flex justify-end gap-2">
                        {BASCULES.map(({ role, teinte }) => (
                          <Bascule
                            key={role}
                            role={role}
                            teinte={teinte}
                            etat={compte.roles[role]}
                            enCours={enCours === `${compte.userId}:${role}`}
                            onClick={() => basculer(compte, role)}
                          />
                        ))}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {tronquee && (
        <p className="text-[12.5px]" style={{ color: C.orange }}>
          Seuls les comptes les plus récents sont listés. Les porteurs d’un rôle apparaissent
          toujours, où qu’ils soient dans la liste.
        </p>
      )}

      <p className="text-[12.5px] text-muted-foreground">
        Les comptes marqués <span className="font-mono">ADMIN_USER_IDS</span> tiennent leur
        administration de la configuration du serveur : elle amorce l’accès sur un environnement
        neuf et se retire en modifiant le <span className="font-mono">.env</span>, puis en
        redéployant. Vous ne pouvez pas retirer votre propre administration — demandez-le à un autre
        administrateur.
      </p>
    </div>
  );
}
