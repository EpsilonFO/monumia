import { useState } from 'react';
import { useNavigate } from 'react-router';
import { LogoMonumia } from '@/components/icons';
import { PaywallDialog } from '@/components/shared/Paywall';
import { Picto } from '@/components/shared/ecrans/Picto';
import { ApercuFiche } from '@/components/monument/nouveau/ApercuFiche';
import { FicheMonumentSections } from '@/components/monument/nouveau/FicheMonumentSections';
import { RechercheMerimee } from '@/components/monument/nouveau/RechercheMerimee';
import { useAuthStore } from '@/stores/useAuthStore';
import { useMonumentStore } from '@/stores/useMonumentStore';
import { useBrouillonInviteStore } from '@/stores/useBrouillonInviteStore';
import { monumentService } from '@/services/monument.service';
import { merimeeService } from '@/services/merimee.service';
import { aideService } from '@/services/aide.service';
import { ApiError } from '@/lib/api-error';
import {
  appliquerMerimee,
  avecTypesEdifice,
  champsARemplir,
  champsManquants,
  ficheDepuisMerimee,
  proprietairesCoches,
  typesCoches,
  typesEdificeDepuisDenomination,
  typesEdificeDepuisNom,
  type FicheMonument,
} from '@/lib/fiche-monument';
import { ROUTES } from '@/constants/routes';
import { toast } from 'sonner';
import type { MerimeeRecord, MonumentInput } from '@/types';
import '@/components/shared/ecrans/ecrans.css';
import './nouveau-monument.css';

/** D'où vient la fiche : la recherche Mérimée ouverte, ou une notice choisie. */
type Source = 'recherche' | 'merimee';

/**
 * Création d'un MONUMENT : sa fiche, état sanitaire inclus, sur un seul écran
 * (maquette « monumia-nouveau-monument » du designer). Rien du chantier ici :
 * les travaux, les intentions et le questionnaire appartiennent au projet et se
 * saisissent dans le wizard projet, une fois le monument décrit.
 *
 * Tout le formulaire est là dès l'arrivée, la recherche Mérimée en tête et
 * mise en avant : choisir une notice pré-remplit la fiche et encadre en orange
 * ce qui reste à dire (l'état du bâtiment toujours, que Mérimée ignore). Rien
 * n'oblige à passer par elle : on peut remplir les champs directement.
 *
 * Le type d'édifice suit le NOM tant que l'utilisateur ne l'a pas choisi
 * lui-même : « Château de Paley » coche « Château » (`typesEdificeDepuisNom`).
 *
 * Page PUBLIQUE, et c'est le pivot du parcours découverte : un visiteur y
 * décrit son bien sans compte, le brouillon partant dans le `localStorage`
 * (cf. `useBrouillonInviteStore`) plutôt qu'en base. Un connecté, lui, crée
 * son monument pour de vrai. Le critère est `user && token`, exactement celui
 * de `ProtectedRoute` : `App.tsx` attend le rafraîchissement de session avant
 * de rendre le router, donc un profil persisté dont le refresh échoue compte
 * bien comme un visiteur.
 *
 * Sortie : le wizard projet. Dans les deux cas, car un monument sans chantier ne
 * mène à aucun diagnostic, et faire atterrir sur la fiche laissait
 * l'utilisateur devant un onglet vide à re-cliquer.
 *
 * L'édition d'un monument existant (`MonumentDetailPage`) garde `MonumentForm`.
 */
export function MonumentWizardPage() {
  const navigate = useNavigate();
  const connecte = useAuthStore((s) => Boolean(s.user && s.token));
  const addMonument = useMonumentStore((s) => s.addMonument);
  const setActiveMonument = useMonumentStore((s) => s.setActiveMonument);
  const brouillonMonument = useBrouillonInviteStore((s) => s.monument);
  const setBrouillonMonument = useBrouillonInviteStore((s) => s.setMonument);

  // Un visiteur qui revient (F5, onglet fermé, « Précédent » depuis le wizard
  // projet) retrouve sa fiche. La valeur est lue une fois, à l'initialisation :
  // la page est ensuite maîtresse de son propre état.
  const [fiche, setFiche] = useState<FicheMonument>(() => brouillonMonument ?? {});
  const [source, setSource] = useState<Source>(() =>
    brouillonMonument?.referenceMerimee ? 'merimee' : 'recherche',
  );
  // Vrai tant que le type d'édifice n'a été ni choisi à la main, ni donné par
  // la dénomination d'une notice : il se déduit alors du nom, à chaque frappe.
  const [typesDepuisNom, setTypesDepuisNom] = useState(
    () => typesCoches(brouillonMonument ?? {}).length === 0,
  );
  const [chargementNotice, setChargementNotice] = useState(false);
  const [saving, setSaving] = useState(false);
  const [paywallOuvert, setPaywallOuvert] = useState(false);

  const update = (maj: FicheMonument) => {
    // Le menu du type d'édifice est la seule écriture de `typeEdifice` sans le
    // nom : l'utilisateur a choisi, le nom ne décide plus.
    const typesChoisis = 'typeEdifice' in maj && !('nom' in maj);
    if (typesChoisis) setTypesDepuisNom(false);
    setFiche((prev) => {
      const suivante = { ...prev, ...maj };
      if (typesChoisis || !('nom' in maj) || !typesDepuisNom) return suivante;
      return { ...suivante, ...avecTypesEdifice(suivante, typesEdificeDepuisNom(maj.nom)) };
    });
  };

  const handleMerimeeSelect = async (searchRecord: MerimeeRecord) => {
    setChargementNotice(true);
    try {
      const fullRecord = await merimeeService.getByReference(searchRecord.reference);
      const notice = ficheDepuisMerimee(fullRecord ?? searchRecord);
      setFiche((prev) => appliquerMerimee(prev, notice));
      // Types tirés du thésaurus : ils font foi. Tirés du nom (ou aucun) : le
      // nom continue de les piloter si on le corrige.
      const record = fullRecord ?? searchRecord;
      setTypesDepuisNom(typesEdificeDepuisDenomination(record.denomination_de_l_edifice).length === 0);
      setSource('merimee');
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Erreur lors de la récupération de la fiche Mérimée',
      );
    } finally {
      setChargementNotice(false);
    }
  };

  const handleFormSubmit = async () => {
    // Le bouton est désactivé tant qu'il manque un champ requis : ce garde ne
    // sert que contre un appel qui passerait outre.
    if (champsManquants(fiche).length > 0) return;
    const data = fiche;
    const payload: MonumentInput = {
      nom: data.nom ?? 'Mon monument',
      commune: data.commune ?? '',
      codeInsee: data.codeInsee ?? '',
      protection: data.protection ?? 'non_protege',
      // Le formulaire impose le type de propriétaire (champ requis) : ce
      // repli ne sert qu'à satisfaire le type.
      proprietaire: proprietairesCoches(data).length
        ? proprietairesCoches(data)
        : ['prive_personne_physique'],
      referenceMerimee: data.referenceMerimee,
      dateProtection: data.dateProtection,
      typeProtection: data.typeProtection,
      siecleConstruction: data.siecleConstruction,
      descriptionGenerale: data.descriptionGenerale,
      etatConservation: data.etatConservation,
      // `?? undefined` : une fiche sans type n'envoie aucune de ces clés (le
      // `null` d'une désélection ne sert qu'à effacer sur une fiche existante).
      typeEdifice: typesCoches(data).length > 0 ? typesCoches(data) : undefined,
      affecteAuCulte: data.affecteAuCulte ?? undefined,
      architectureRomane: data.architectureRomane ?? undefined,
      // Lu par le seul diagnostic invité ; la création le relit en base.
      merimeeDomaine: data.merimeeDomaine ?? undefined,
    };

    setSaving(true);
    try {
      if (!connecte) {
        // Dry-run du diagnostic invité : rien ne s'enregistre, mais la commune
        // est RÉSOLUE côté serveur (400 si elle est introuvable). La valider
        // maintenant est le seul moment utile : plus tard, le 400 tomberait au
        // rejeu, après l'inscription, sur un brouillon qu'on ne peut plus
        // corriger.
        await aideService.runDiagnosticInvite({
          monument: payload,
          travauxEnvisages: [],
          answers: {},
        });
        setBrouillonMonument(payload);
        navigate(ROUTES.PROJET_NEW_INVITE);
        return;
      }

      const created = await monumentService.create(payload);
      addMonument(created);
      setActiveMonument(created.id);
      navigate(ROUTES.PROJET_NEW(created.id));
    } catch (err) {
      // 402 : le compte a déjà son monument gratuit. Atteignable depuis la
      // landing (les CTA mènent ici sans savoir qui est connecté), donc traité
      // comme une porte et non comme une panne.
      if (err instanceof ApiError && err.status === 402) {
        setPaywallOuvert(true);
      } else {
        toast.error(err instanceof Error ? err.message : 'Erreur lors de la création du monument');
      }
    } finally {
      setSaving(false);
    }
  };

  // Quitter : vers l'espace pour un connecté, vers la connexion pour un
  // visiteur (il n'a pas d'espace, et son brouillon l'attend ici). Sans
  // confirmation, comme avant la refonte.
  const quitterVers = connecte ? ROUTES.MONUMENTS : '/login';

  const blocMerimee =
    source === 'recherche' ? (
      <div className="fld merimee-avant">
        <label htmlFor="nm-merimee">
          <Picto nom="loupe" />
          Gagnez du temps&nbsp;: cherchez votre monument dans la base Mérimée
        </label>
        <p className="why">
          S&rsquo;il est protégé, il y figure&nbsp;: choisissez-le et les champs ci-dessous se
          rempliront tout seuls. Sinon, remplissez-les directement.
        </p>
        <RechercheMerimee
          id="nm-merimee"
          onSelect={handleMerimeeSelect}
          chargement={chargementNotice}
        />
      </div>
    ) : (
      <div className="fld">
        <span className="lb">Base Mérimée</span>
        <div className="ac-alt">
          <span className="ac-ok">
            <Picto nom="coche" />
            Fiche pré-remplie depuis la notice
            {fiche.referenceMerimee ? ` ${fiche.referenceMerimee}` : ''}
          </span>
          <button type="button" className="lnk" onClick={() => setSource('recherche')}>
            <Picto nom="loupe" />
            Chercher un autre monument
          </button>
        </div>
      </div>
    );

  return (
    <div className="ec nm-page">
      <header className="w bar">
        <button
          type="button"
          className="logo"
          onClick={() => navigate(quitterVers)}
          aria-label="Quitter"
        >
          <LogoMonumia className="logo-m" />
          <span className="logo-t">Monumia</span>
        </button>
        <button type="button" className="quit" onClick={() => navigate(quitterVers)}>
          <Picto nom="croix" />
          Quitter
        </button>
      </header>

      <main className="w">
        <div className="head">
          <span className="eyebrow nu o">Nouveau monument</span>
          <h1>La fiche de votre monument</h1>
          <p>
            Ces informations servent à <b>trier les aides pour vous</b>. Vous ne les donnez
            qu&rsquo;une fois&nbsp;: elles valent pour tous vos projets sur ce monument.
          </p>
        </div>

        <div className="grid">
          <form noValidate onSubmit={(e) => e.preventDefault()}>
            <FicheMonumentSections
              fiche={fiche}
              onChange={update}
              merimee={blocMerimee}
              // Les encadrés ne viennent qu'après un pré-remplissage : sur une
              // fiche vide, tout serait orange et plus rien ne se verrait.
              aRemplir={source === 'merimee' ? champsARemplir(fiche) : undefined}
            />
          </form>
          <ApercuFiche fiche={fiche} saving={saving} onValider={handleFormSubmit} />
        </div>
      </main>

      {/* Le compte a déjà son monument gratuit. En MODALE et non en toast :
          c'est une porte, et on referme sur son formulaire intact plutôt que
          d'être expédié sur la page des tarifs. */}
      <PaywallDialog
        open={paywallOuvert}
        onOpenChange={setPaywallOuvert}
        offre="Multi-monuments"
        titre="Un deuxième monument, et tous les suivants"
        description="L'offre gratuite couvre un monument. Multi-monuments lève la limite, réunit tous vos biens sur un tableau de bord et ouvre les suppressions."
      />
    </div>
  );
}
