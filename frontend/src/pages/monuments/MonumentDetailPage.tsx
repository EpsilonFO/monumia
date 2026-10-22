import { useState, useMemo, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams, Link, useNavigate, useSearchParams } from 'react-router';
import { ChevronLeft, Loader2 } from 'lucide-react';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { MonumentForm } from '@/components/monument/MonumentForm';
import { MonumentFiche } from '@/components/monument/MonumentFiche';
import { EnTeteMonument } from '@/components/monument/EnTeteMonument';
import { Onglets, type Onglet } from '@/components/shared/ecrans/Onglets';
import { Picto } from '@/components/shared/ecrans/Picto';
import { ProjetCard } from '@/components/projet/ProjetCard';
import { OngletDocuments } from '@/components/document/OngletDocuments';
import { TeamPanel } from '@/components/sharing/TeamPanel';
import { projectPermissions } from '@/lib/project-permissions';
import { ProjectDetailSkeleton } from '@/components/skeletons';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useProjetStore } from '@/stores/useProjetStore';
import { useDossierStore } from '@/stores/useDossierStore';
import { useAideStore } from '@/stores/useAideStore';
import { useSuiviStore } from '@/stores/useSuiviStore';
import { monumentService } from '@/services/monument.service';
import { projetService } from '@/services/projet.service';
import { documentService } from '@/services/document.service';
import { dossierService } from '@/services/dossier.service';
import { sharingService } from '@/services/sharing.service';
import { computeMonumentStats, computeProjectStats, projectStage } from '@/lib/project-stats';
import './monument.css';
import { useOffre, useOffreMonument, useOffreMonumentConnue } from '@/hooks/useOffre';
import { libelleMonuments, sousLePlafond } from '@/lib/offres';
import { PaywallDialog, PaywallOverlay } from '@/components/shared/Paywall';
import { C, SERIF } from '@/lib/brand';
import { isAccessLostError } from '@/lib/api-error';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import type { Monument, Document, ProjectMember, ProjectInvitation } from '@/types';
import { BoutonRetour } from '@/components/shared/ecrans/BoutonRetour';
import { Guide } from '@/components/shared/Guide';

/**
 * Page d'un MONUMENT : la fiche du bien et tout ce qui s'y rattache
 * durablement — sa fiche sanitaire, ses projets de travaux, ses documents, son
 * équipe. Les aides et les dossiers, eux, appartiennent à un chantier précis et
 * vivent sur la page du projet.
 */
export function MonumentDetailPage() {
  const { t } = useTranslation(['monuments', 'common']);
  const { monumentId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const monument = useMonumentStore((s) => s.monuments.find((m) => m.id === monumentId));
  const upsertMonument = useMonumentStore((s) => s.upsertMonument);
  const updateMonument = useMonumentStore((s) => s.updateMonument);
  const deleteMonument = useMonumentStore((s) => s.deleteMonument);

  const allProjets = useProjetStore((s) => s.projets);
  const setProjets = useProjetStore((s) => s.setProjets);
  const projets = useMemo(
    () => allProjets.filter((p) => p.monumentId === monumentId),
    [allProjets, monumentId],
  );

  const allDossiers = useDossierStore((s) => s.dossiers);
  const dossiers = useMemo(
    () => allDossiers.filter((d) => d.monumentId === monumentId),
    [allDossiers, monumentId],
  );

  const digestsByProjet = useAideStore((s) => s.digestsByProjet);
  const suivis = useSuiviStore((s) => s.suivis);

  // Documents du monument : on charge TOUS les documents qui y sont rattachés
  // (tous les membres confondus) via le fetch monument-scopé, pas le store « mes
  // documents ». Sans ça, un owner/co_owner ne verrait jamais les pièces déposées
  // par un collaborateur.
  const [monumentDocuments, setMonumentDocuments] = useState<Document[]>([]);

  const [notFound, setNotFound] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [invitations, setInvitations] = useState<ProjectInvitation[]>([]);
  const [paywallProjet, setPaywallProjet] = useState(false);

  // L'offre qui gouverne CE bien, et non celle du compte : un architecte
  // invité par un client abonné doit pouvoir lancer un chantier de plus.
  const offre = useOffreMonument(monumentId);
  // Faux tant que le monument vient du cache local, qui ne garde ni son offre
  // ni le rôle de l'utilisateur : rien de ce qu'ils gouvernent ne se tranche
  // avant la réponse du serveur.
  const droitsConnus = useOffreMonumentConnue(monumentId);
  // Le fil d'Ariane remonte à l'espace du COMPTE : c'est son plafond à lui
  // qui décide du singulier, pas l'offre qui gouverne ce monument-ci.
  const offreCompte = useOffre();
  const peutCreerProjet = sousLePlafond(offre.projetsMax, projets.length);

  // Travailler à plusieurs est un service de l'offre Veille. L'onglet Équipe
  // reste VISIBLE au gratuit — c'est une porte, pas un vide — mais il mène aux
  // tarifs plutôt qu'à un formulaire que le serveur refuserait (402).
  //
  // Il s'ouvre quand même si une équipe existe déjà, et ce n'est pas une
  // politesse : après une résiliation, les collaborateurs gardent leur accès.
  // Renvoyer alors vers les tarifs le rendrait irrévocable. On laisse donc
  // gérer ce qui est là, sans pouvoir y ajouter (cf. TeamPanel).
  const equipeAccessible = offre.equipe || members.length > 1 || invitations.length > 0;

  const tabParam = searchParams.get('tab');
  // Onglet par défaut : les Projets. Ouvrir un monument sert le plus souvent à
  // reprendre un chantier ; la fiche, elle, ne bouge quasiment plus une fois
  // remplie.
  const requestedTab =
    tabParam === 'sanitaire' || tabParam === 'documents' || tabParam === 'equipe'
      ? tabParam
      : 'projets';
  const handleTabChange = useCallback((value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', value);
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  // Rafraîchir au montage (et quand on change de monument) : revenir sur la page
  // doit refléter les changements des autres membres, sans recharger le navigateur.
  useEffect(() => {
    if (!monumentId) return;
    monumentService.getById(monumentId)
      .then(upsertMonument)
      .catch(() => {
        if (!useMonumentStore.getState().monuments.some((m) => m.id === monumentId)) {
          setNotFound(true);
        }
      });
  }, [monumentId, upsertMonument]);

  // Les projets du monument : rafraîchis à l'arrivée, fusionnés dans le store
  // global (qui porte aussi ceux des autres monuments, chargés par le dashboard).
  useEffect(() => {
    if (!monumentId) return;
    projetService
      .listByMonument(monumentId)
      .then((rows) => {
        const autres = useProjetStore.getState().projets.filter((p) => p.monumentId !== monumentId);
        setProjets([...rows, ...autres]);
      })
      .catch(console.error);
  }, [monumentId, setProjets]);

  useEffect(() => { dossierService.fetchAll().catch(console.error); }, []);

  // Réservé à l'équipe du monument : la route refuse les accès par projet, et
  // l'appeler pour rien afficherait une erreur dans la console à chaque visite.
  const peutVoirLeMonument = !!monument?.myRole;
  const reloadMonumentDocuments = useCallback(() => {
    if (!monumentId || !peutVoirLeMonument) return;
    documentService.getAll({ monumentId }).then(setMonumentDocuments).catch(() => {});
  }, [monumentId, peutVoirLeMonument]);
  useEffect(() => { reloadMonumentDocuments(); }, [reloadMonumentDocuments]);

  const reloadMembers = useCallback(() => {
    if (!monumentId || !peutVoirLeMonument) return;
    sharingService
      .getMembers(monumentId)
      .then((data) => {
        setMembers(data.members);
        setInvitations(data.invitations);
      })
      .catch((err) => {
        // Perte d'accès définitive (monument supprimé par le chef, membre retiré,
        // ou départ déjà effectué) : on purge le cache local et on bascule sur
        // l'écran « introuvable ». Sur une erreur transitoire (réseau, 5xx), on
        // ne touche à rien pour ne pas éjecter l'utilisateur à tort.
        if (isAccessLostError(err)) {
          deleteMonument(monumentId);
          setNotFound(true);
        }
      });
  }, [monumentId, peutVoirLeMonument, deleteMonument]);
  useEffect(() => { reloadMembers(); }, [reloadMembers]);

  const uploaderNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const m of members) map[m.userId] = `${m.prenom} ${m.nom}`.trim();
    return map;
  }, [members]);

  // Un onglet réservé à l'équipe du monument demandé par quelqu'un qui n'en est
  // pas membre retombe sur l'onglet par défaut : le serveur refuserait de toute
  // façon. Même repli pour l'onglet Équipe hors offre — arriver par un lien
  // gardé en favori affiche le monument, là où un clic délibéré mène aux
  // tarifs : on n'éjecte pas quelqu'un qui voulait simplement ouvrir sa fiche.
  //
  // Pas de repli tant que les droits sont inconnus : un monument relu du cache
  // n'a pas de `myRole`, et ce n'est pas un accès restreint. Retomber sur les
  // Projets pour revenir aussitôt sur l'onglet demandé ferait sauter la page.
  const activeTab =
    (droitsConnus && !monument?.myRole && (requestedTab === 'documents' || requestedTab === 'equipe'))
      ? 'projets'
      : requestedTab;

  const stats = useMemo(
    () => (monument ? computeMonumentStats(monument, projets, digestsByProjet, dossiers) : null),
    [monument, projets, digestsByProjet, dossiers],
  );

  const dossierNames = useMemo(
    () => Object.fromEntries(allDossiers.map((d) => [d.id, d.titre])),
    [allDossiers],
  );

  // Le bouton garde son libellé et son geste, et c'est le paywall qui se pose
  // devant quand le plafond est atteint : refermer la modale laisse
  // l'utilisateur là où il était, ce qu'une redirection vers les tarifs ne
  // permet pas.
  //
  // Tant que l'offre n'est pas revenue du serveur, le clic ne tranche pas : le
  // plafond par défaut est celui du gratuit, et un abonné qui clique dans la
  // première seconde se verrait proposer une offre qu'il a déjà.
  const goNouveauProjet = useCallback(() => {
    if (!droitsConnus) return;
    if (!peutCreerProjet) {
      setPaywallProjet(true);
      return;
    }
    if (monumentId) navigate(ROUTES.PROJET_NEW(monumentId));
  }, [droitsConnus, peutCreerProjet, monumentId, navigate]);

  if (notFound || (!monument && !monumentId)) {
    return (
      <div className="space-y-4">
        <h1 className="text-[23px]" style={{ fontFamily: SERIF, color: C.ink }}>{t('MonumentDetailPage.introuvable')}</h1>
        <p className="text-[16px] text-muted-foreground">{t('MonumentDetailPage.introuvableTexte')}</p>
        <Link to={ROUTES.MONUMENTS} className="inline-flex items-center gap-1.5 text-[15px] font-medium" style={{ color: C.blue }}>
          <ChevronLeft className="h-3.5 w-3.5" /> {t('MonumentDetailPage.retourMesMonuments')}
        </Link>
      </div>
    );
  }

  if (!monument || !stats) return <ProjectDetailSkeleton />;

  const handleSave = async (data: Partial<Monument>) => {
    setSaving(true);
    try {
      const updated = await monumentService.update(monument.id, data);
      updateMonument(monument.id, updated);
      setIsEditing(false);
      toast.success(t('MonumentDetailPage.misAJour'));
    } catch (err) { toast.error(err instanceof Error ? err.message : t('MonumentDetailPage.erreurSauvegarde')); }
    finally { setSaving(false); }
  };

  const handleRenommer = async (nom: string) => {
    try {
      updateMonument(monument.id, await monumentService.update(monument.id, { nom }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('MonumentDetailPage.erreurRenommage'));
      throw err;
    }
  };

  // Supprimer le monument emporte ses projets, dossiers et suivis (cascade en
  // base). Les dossiers sont supprimés d'abord pour que le store local reste
  // cohérent si la suppression du monument échoue à mi-chemin.
  const handleDelete = async () => {
    setConfirmDeleteOpen(false);
    setDeleting(true);
    try {
      for (const dossier of dossiers) await dossierService.delete(dossier.id);
      await monumentService.delete(monument.id);
      deleteMonument(monument.id);
      toast.success(t('MonumentDetailPage.supprime'));
      navigate(ROUTES.MONUMENTS);
    } catch (err) { toast.error(err instanceof Error ? err.message : t('MonumentDetailPage.erreurSuppression')); }
    finally { setDeleting(false); }
  };


  if (isEditing) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <button onClick={() => setIsEditing(false)} className="inline-flex items-center gap-1.5 text-[15px] font-medium" style={{ color: C.blue }}>
            <ChevronLeft className="h-3.5 w-3.5" /> {t('common:actions.retour')}
          </button>
          <h1 className="text-[20.5px]" style={{ fontFamily: SERIF, color: C.ink }}>{t('MonumentDetailPage.modifierTitre', { nom: monument.nom })}</h1>
        </div>
        <MonumentForm initialData={monument} onSubmit={handleSave} isEditing saving={saving} />
      </div>
    );
  }

  const canEdit = projectPermissions(monument.myRole ?? null).canEditProject;
  // `myRole` nul = accès obtenu via UN de ses projets : la fiche sanitaire est
  // lisible, le reste du monument non (cf. require_monument_read côté serveur).
  // L'onglet Projets ne liste alors que les chantiers de la personne, filtrés
  // par l'API — on masque simplement ce qui n'a pas de contenu pour elle.
  // Tant que les droits ne sont pas revenus du serveur (monument relu du cache
  // local, sans `myRole`), on ne sait pas encore : les onglets restent, comme
  // le repli de `activeTab` plus haut. Les masquer puis les faire réapparaître
  // faisait sauter la barre, et ils manquaient si la relecture échouait.
  const equipeDuMonument = !droitsConnus || !!monument.myRole;

  // Monté une seule fois, que l'offre l'ouvre ou non : c'est le même panneau,
  // seul son habillage change.
  const equipePanel = (
    <TeamPanel
      scope="monument"
      scopeId={monument.id}
      invitationsOuvertes={offre.equipe}
      myRole={monument.myRole ?? null}
      members={members}
      invitations={invitations}
      onChanged={reloadMembers}
      onLeft={() => { deleteMonument(monument.id); navigate(ROUTES.MONUMENTS); }}
    />
  );

  const tabs: Onglet<string>[] = [
    { value: 'sanitaire', label: t('MonumentDetailPage.onglets.fiche'), picto: 'maison', count: null, guide: 'monument.onglet-fiche' },
    { value: 'projets', label: t('MonumentDetailPage.onglets.projets'), picto: 'dossier', count: projets.length, guide: 'monument.onglet-projets' },
    ...(equipeDuMonument
      ? [
          {
            value: 'documents',
            label: t('MonumentDetailPage.onglets.documents'),
            picto: 'doc' as const,
            count: monumentDocuments.length,
            guide: 'monument.onglet-documents',
          },
          {
            value: 'equipe',
            label: t('MonumentDetailPage.onglets.equipe'),
            picto: 'equipe' as const,
            count: members.length,
            guide: 'monument.onglet-equipe',
          },
        ]
      : []),
  ];

  return (
    <div className="ec pmon">
      <Guide id="monument" pret={droitsConnus} />
      <BoutonRetour to={ROUTES.MONUMENTS} libelle={t('MonumentDetailPage.retourA', { espace: libelleMonuments(offreCompte).toLowerCase() })} />

      <EnTeteMonument
        monument={monument}
        members={members}
        onModifier={canEdit ? () => setIsEditing(true) : undefined}
        onRenommer={canEdit ? handleRenommer : undefined}
      />

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <Onglets onglets={tabs} actif={activeTab} onChange={handleTabChange} label={t('MonumentDetailPage.ongletsAria')} />

        {/* FICHE SANITAIRE */}
        <TabsContent value="sanitaire">
          <MonumentFiche
            monument={monument}
            canEdit={canEdit}
            onEdit={() => setIsEditing(true)}
            // Deux conditions, et elles ne disent pas la même chose : le rôle
            // dit « ce compte a-t-il le droit », l'offre dit « ce produit le
            // permet-il ». Aucune ne remplace l'autre.
            canDelete={
              projectPermissions(monument.myRole ?? null).canDeleteProject &&
              offre.suppressionMonument
            }
            deleting={deleting}
            onDelete={() => setConfirmDeleteOpen(true)}
          />
        </TabsContent>

        {/* PROJETS */}
        <TabsContent value="projets">
          {projets.length > 0 && (
            <>
              <div className="sec-h">
                <div>
                  <h2>{t('MonumentDetailPage.vosProjets')}</h2>
                  <p>{t('MonumentDetailPage.vosProjetsSousTitre')}</p>
                </div>
              </div>
              {projets.map((projet) => (
                <ProjetCard
                  key={projet.id}
                  projet={projet}
                  monumentNom={monument.nom}
                  stats={computeProjectStats(projet, digestsByProjet[projet.id] ?? null, dossiers)}
                  stage={projectStage(
                    digestsByProjet[projet.id] ?? null,
                    dossiers.filter((d) => d.projetId === projet.id),
                    suivis.filter((s) => s.projetId === projet.id),
                  )}
                />
              ))}
            </>
          )}
          {canEdit ? (
            <div className="new" style={projets.length === 0 ? { marginTop: 35 } : undefined}>
              <div>
                <b>
                  {projets.length === 0
                    ? t('MonumentDetailPage.premierProjet')
                    : t('MonumentDetailPage.autreChantier')}
                </b>
                <p>{t('MonumentDetailPage.projetExplication')}</p>
              </div>
              <button className="btn b-orange" type="button" onClick={goNouveauProjet}>
                <Picto nom="plus" />
                {t('MonumentDetailPage.nouveauProjet')}
              </button>
            </div>
          ) : (
            projets.length === 0 && (
              <p className="vide" style={{ marginTop: 40 }}>
                {t('MonumentDetailPage.aucunProjet')}
              </p>
            )
          )}
        </TabsContent>

        {/* DOCUMENTS */}
        <TabsContent value="documents" className="onglet">
          {/* Réservé à l'équipe du monument (cf. `activeTab`) : la liste vient de
              `documentService.getAll({ monumentId })`, tous membres confondus,
              et porte aussi les pièces de ses projets (pastille du chantier). */}
          <OngletDocuments
            ici={{ type: 'monument', id: monument.id, nom: monument.nom }}
            monumentId={monument.id}
            documents={monumentDocuments}
            onChange={reloadMonumentDocuments}
            role={monument.myRole ?? null}
            auteurs={uploaderNames}
            dossierNames={dossierNames}
            intro={t('MonumentDetailPage.documentsIntro')}
            vide={t('MonumentDetailPage.documentsVide')}
          />
        </TabsContent>

        {/* ÉQUIPE */}
        <TabsContent value="equipe" className="onglet">
          {equipeAccessible ? (
            equipePanel
          ) : !droitsConnus ? (
            // Offre pas encore connue : ni formulaire ni paywall.
            <div className="flex justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin" style={{ color: C.blueLight }} />
            </div>
          ) : (
            <PaywallOverlay
              offre="Veille"
              titre={t('MonumentDetailPage.paywallEquipe.titre')}
              description={t('MonumentDetailPage.paywallEquipe.description')}
              monumentId={monument.id}
            >
              {equipePanel}
            </PaywallOverlay>
          )}
        </TabsContent>
      </Tabs>


      <PaywallDialog
        open={paywallProjet}
        onOpenChange={setPaywallProjet}
        offre="Veille"
        titre={t('MonumentDetailPage.paywallProjet.titre')}
        description={
          offre.projetsMax === null
            ? t('MonumentDetailPage.paywallProjet.descriptionIllimite')
            : t('MonumentDetailPage.paywallProjet.descriptionPlafond', { max: offre.projetsMax })
        }
        monumentId={monument.id}
      />

      <AlertDialog open={confirmDeleteOpen} onOpenChange={setConfirmDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('MonumentDetailPage.supprimerTitre', { nom: monument.nom })}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('MonumentDetailPage.supprimerDescription')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>{t('common:actions.annuler')}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleDelete} disabled={deleting}>
              {deleting ? t('MonumentDetailPage.suppression') : t('common:actions.supprimer')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
