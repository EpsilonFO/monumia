import { useEffect, useMemo, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { IconRecherche } from '@/components/icons';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { adminService } from '@/services/admin.service';
import { useAuthStore } from '@/stores/useAuthStore';
import { localeIntl } from '@/i18n/format';
import { filtrerUtilisateurs } from '@/lib/admin-catalogue';
import { C } from '@/lib/brand';
import type { EtatRole, RoleCompte, UtilisateurAdmin } from '@/types/admin.types';

interface Props {
  onErreur: (err: unknown, repli: string) => void;
}

/**
 * Les deux bascules, dans l'ordre des colonnes. La couleur dit laquelle :
 * l'orange de l'accent pour le bêta-test, le bleu institutionnel pour
 * l'administration — la plus lourde des deux.
 */
const BASCULES: { role: RoleCompte; teinte: string }[] = [
  { role: 'beta_testeur', teinte: C.orangeVif },
  { role: 'admin', teinte: C.blue },
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
  const { t } = useTranslation(['admin', 'common']);
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!etat.modifiable || enCours}
      // `raison` vient du serveur et dit POURQUOI c'est bloqué : un bouton
      // grisé sans explication est une impasse.
      title={etat.raison ?? undefined}
      aria-pressed={etat.actif}
      className="w-36 shrink-0 rounded-lg border px-3 py-1.5 text-[15px] font-medium transition-all disabled:cursor-not-allowed disabled:opacity-45"
      style={
        etat.actif
          ? { background: teinte, borderColor: teinte, color: '#fff' }
          : { borderColor: C.border, color: C.grayFg }
      }
    >
      {enCours ? '…' : t(`AdminRolesPanel.roles.${role}`)}
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
  const { t } = useTranslation(['admin', 'common']);
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
      .catch((err) => onErreur(err, t('AdminRolesPanel.listeIndisponible')))
      .finally(() => {
        if (!annule) setChargement(false);
      });
    return () => {
      annule = true;
    };
  }, [onErreur, t]);

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
      const nom = intitule(compte);
      toast.success(
        etat.actif
          ? t(`AdminRolesPanel.toastRetire.${role}`, { nom })
          : t(`AdminRolesPanel.toastAttribue.${role}`, { nom }),
      );
    } catch (err) {
      onErreur(err, t('AdminRolesPanel.changementImpossible'));
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
            placeholder={t('AdminRolesPanel.recherche')}
            className="h-10 pl-9 text-[16px]"
          />
        </div>
        <p className="text-[15px] text-muted-foreground">
          {t('AdminRolesPanel.nbComptes', { count: utilisateurs.length })}
          {compteurs.map(({ role, nb }) => (
            <span key={role}> · {t(`AdminRolesPanel.compteurRole.${role}`, { count: nb })}</span>
          ))}
        </p>
      </div>

      <p className="text-[14.5px] text-muted-foreground">
        <Trans
          t={t}
          i18nKey="AdminRolesPanel.explication"
          components={{ gras: <span className="font-medium text-foreground" /> }}
        />
      </p>

      <div className="overflow-hidden rounded-xl border border-border bg-card">
        {chargement ? (
          <p className="px-4 py-8 text-center text-[16px] text-muted-foreground">{t('common:etats.chargement')}</p>
        ) : visibles.length === 0 ? (
          <p className="px-4 py-8 text-center text-[16px] text-muted-foreground">
            {t('AdminRolesPanel.aucunResultat')}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('AdminRolesPanel.colonnes.compte')}</TableHead>
                  <TableHead className="hidden lg:table-cell">
                    {t('AdminRolesPanel.colonnes.inscrit')}
                  </TableHead>
                  <TableHead className="text-right">{t('AdminRolesPanel.colonnes.roles')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibles.map((compte) => (
                  <TableRow key={compte.userId}>
                    <TableCell>
                      <p className="font-medium text-foreground">
                        {intitule(compte)}
                        {compte.userId === moi && (
                          <span className="ml-2 text-[14px] font-normal text-muted-foreground">
                            {t('AdminRolesPanel.vous')}
                          </span>
                        )}
                      </p>
                      <p className="text-[14.5px] text-muted-foreground">
                        {compte.email ?? <span className="font-mono">{compte.userId}</span>}
                      </p>
                      {(compte.compteIntrouvable || compte.roles.admin.source === 'socle') && (
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {compte.roles.admin.source === 'socle' && (
                            <Badge variant="outline" title={t('AdminRolesPanel.socleTitle')}>
                              ADMIN_USER_IDS
                            </Badge>
                          )}
                          {compte.compteIntrouvable && (
                            <Badge variant="destructive">{t('AdminRolesPanel.compteIntrouvable')}</Badge>
                          )}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="hidden lg:table-cell text-[15px] text-muted-foreground">
                      {compte.createdAt
                        ? new Date(compte.createdAt).toLocaleDateString(localeIntl())
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
        <p className="text-[14.5px]" style={{ color: C.orange }}>
          {t('AdminRolesPanel.listeTronquee')}
        </p>
      )}

      <p className="text-[14.5px] text-muted-foreground">
        <Trans
          t={t}
          i18nKey="AdminRolesPanel.socleExplication"
          components={{ code: <span className="font-mono" /> }}
        />
      </p>
    </div>
  );
}
