"""Tests des primitives texte de la veille (scripts/veille_text.py).

Les cas ne sont pas synthétiques : ce sont les divergences réellement
rencontrées entre les quotes des YAML et leurs snapshots (apostrophes courbes
des CMS, insécables avant « : » et « % », texte désaccentué par pdftotext,
block scalars YAML repliés sur plusieurs lignes).

Run from backend/:  uv run pytest tests/test_veille_text.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from veille_text import (  # noqa: E402
    find_quote,
    find_quote_in_any,
    flatten_markdown_links,
    is_cosmetic_change,
    is_noise_line,
    normalize,
    normalize_lines,
    normalize_with_offsets,
    normalized_diff,
    parse_front_matter,
    strip_front_matter,
)


class TestNormalize(unittest.TestCase):
    def test_apostrophes_courbes_et_droites_convergent(self):
        self.assertEqual(normalize("l’édifice"), normalize("l'edifice"))

    def test_guillemets_convergent(self):
        # Les guillemets se replient sur `"`. L'espace intérieur de l'usage
        # français n'est PAS supprimé : effondrer les blancs autour d'un
        # guillemet ferait matcher des découpages de phrase différents.
        self.assertEqual(normalize("« gros œuvre »"), normalize("“ gros oeuvre ”"))
        self.assertEqual(normalize('"charpente"'), normalize("“charpente”"))

    def test_tirets_typographiques_convergent(self):
        self.assertEqual(normalize("1er septembre — 31 octobre"), "1er septembre - 31 octobre")
        self.assertEqual(normalize("aide – montant"), normalize("aide - montant"))

    def test_ellipse_devient_trois_points(self):
        self.assertEqual(normalize("de vitraux…"), "de vitraux...")

    def test_espace_typographique_avant_ponctuation_efface(self):
        # L'insécable avant « : » et « % » est systématique dans les CMS
        # français, absente des PDF et de la plupart des saisies manuelles.
        # Mesuré sur les 142 aides : c'était la première cause de quotes
        # authentiques déclarées absentes.
        self.assertEqual(normalize("charpente : 80 %"), "charpente: 80%")
        self.assertEqual(normalize("taux de 50 %"), normalize("taux de 50%"))
        self.assertEqual(normalize("Travaux :"), normalize("Travaux:"))

    def test_espace_parasite_de_pdftotext_avant_ponctuation(self):
        # `pdftotext` insère des blancs devant virgules et parenthèses fermantes.
        self.assertEqual(
            normalize("(capital et intérêt) , les petites"),
            normalize("(capital et intérêt), les petites"),
        )

    def test_espace_apres_parenthese_ouvrante(self):
        self.assertEqual(normalize("( réserves naturelles"), normalize("(réserves naturelles"))

    def test_espace_significatif_entre_mots_conserve(self):
        # Le resserrement ne concerne QUE la ponctuation : deux mots restent
        # deux mots, sinon des contenus distincts se mettraient à matcher.
        self.assertNotEqual(normalize("non protégé"), normalize("nonprotégé"))

    def test_desaccentuation_aligne_pdftotext(self):
        self.assertEqual(normalize("antérieurs à 1800"), "anterieurs a 1800")

    def test_accent_precompose_et_decompose_convergent(self):
        self.assertEqual(normalize("é"), normalize("é"))

    def test_repli_de_casse(self):
        self.assertEqual(normalize("MONUMENTS Historiques"), "monuments historiques")

    def test_ligature_oe_alignee_sur_oe(self):
        self.assertEqual(normalize("œuvre"), "oeuvre")
        self.assertEqual(normalize("Œuvres d’art"), "oeuvres d'art")

    def test_ligature_fi_decomposee_par_nfkc(self):
        self.assertEqual(normalize("ﬁnancement"), "financement")

    def test_invisibles_supprimes(self):
        # Trait d'union conditionnel et espace sans largeur : semés par les CMS
        # et par pdftotext aux césures, ils ne doivent pas couper un mot.
        self.assertEqual(normalize("restau­ration​"), "restauration")

    def test_blancs_effondres_et_rognes(self):
        self.assertEqual(normalize("  gros   œuvre \n\t charpente  "), "gros oeuvre charpente")

    def test_sauts_de_ligne_deviennent_espace(self):
        # Une quote issue d'un block scalar YAML `>-` est repliée en une ligne :
        # elle doit matcher le même texte réparti sur plusieurs lignes.
        self.assertEqual(normalize("gros œuvre\ncharpente"), "gros oeuvre charpente")

    def test_chaine_vide_et_blancs_purs(self):
        self.assertEqual(normalize(""), "")
        self.assertEqual(normalize("  \n\t "), "")

    def test_idempotence(self):
        source = "L’édifice doit être une église — antérieure à 1800… (80 %)"
        once = normalize(source)
        self.assertEqual(normalize(once), once)


class TestNormalizeWithOffsets(unittest.TestCase):
    def test_offsets_pointent_vers_la_source(self):
        source = "L’édifice"
        norm, offsets = normalize_with_offsets(source)
        self.assertEqual(norm, "l'edifice")
        self.assertEqual(len(norm), len(offsets))
        # Chaque offset désigne le caractère d'origine qui a produit le normalisé.
        self.assertEqual(source[offsets[0]], "L")
        self.assertEqual(source[offsets[1]], "’")

    def test_offsets_monotones_et_dans_les_bornes(self):
        source = "  Travaux :\n\tgros œuvre — 80 % ﬁnancés  "
        norm, offsets = normalize_with_offsets(source)
        self.assertEqual(len(norm), len(offsets))
        self.assertTrue(all(0 <= o < len(source) for o in offsets))
        self.assertEqual(offsets, sorted(offsets))

    def test_expansion_multi_caracteres_partage_un_offset(self):
        # « œ » produit deux caractères normalisés issus d'un seul caractère source.
        norm, offsets = normalize_with_offsets("œuf")
        self.assertEqual(norm, "oeuf")
        self.assertEqual(offsets[0], offsets[1])

    def test_coherence_avec_normalize(self):
        source = "Les travaux doivent concerner le gros œuvre : structure de charpente,"
        self.assertEqual(normalize(source), normalize_with_offsets(source)[0])


class TestNormalizeLines(unittest.TestCase):
    def test_paires_normalisee_et_brute(self):
        # Le diff s'aligne sur la gauche de la paire et s'affiche avec la droite.
        pairs = normalize_lines("  Gros œuvre : charpente\n\n  80 % maximum\n")
        self.assertEqual(
            pairs,
            [("gros oeuvre: charpente", "Gros œuvre : charpente"), ("80% maximum", "80 % maximum")],
        )

    def test_lignes_vides_ecartees(self):
        self.assertEqual(normalize_lines("\n\n   \n\t\n"), [])


class TestFrontMatter(unittest.TestCase):
    SNAPSHOT = (
        "---\n"
        "url: https://www.sauvegardeartfrancais.fr/demander-une-aide/\n"
        "fetched_at: 2026-08-05T13:38:21+00:00\n"
        "sha256: 9d8a55f90d9a49bd1b05cada7df070744809a8bd4bf16599567c1276e46606f6\n"
        "---\n"
        "\n"
        "[Mon compte](https://www.sauvegardeartfrancais.fr/mon-compte/)\n"
    )

    def test_parse_recupere_url_et_sha(self):
        meta, body = parse_front_matter(self.SNAPSHOT)
        self.assertEqual(meta["url"], "https://www.sauvegardeartfrancais.fr/demander-une-aide/")
        self.assertEqual(
            meta["sha256"], "9d8a55f90d9a49bd1b05cada7df070744809a8bd4bf16599567c1276e46606f6"
        )
        # Une URL contient « : » : la valeur ne doit pas être tronquée.
        self.assertIn("https://", meta["url"])
        self.assertTrue(body.lstrip().startswith("[Mon compte]"))

    def test_horodatage_iso_conserve_ses_deux_points(self):
        meta, _ = parse_front_matter(self.SNAPSHOT)
        self.assertEqual(meta["fetched_at"], "2026-08-05T13:38:21+00:00")

    def test_document_sans_en_tete_intact(self):
        body = "# Règlement\n\nLes travaux…\n"
        self.assertEqual(strip_front_matter(body), body)
        self.assertEqual(parse_front_matter(body)[0], {})

    def test_tirets_du_corps_ne_sont_pas_pris_pour_un_en_tete(self):
        # Un `---` en milieu de document ne doit pas amputer le corps.
        body = "Texte\n\n---\n\nSuite\n"
        self.assertEqual(strip_front_matter(body), body)


class TestIsNoiseLine(unittest.TestCase):
    def test_lien_de_navigation_seul(self):
        self.assertTrue(
            is_noise_line("  * [Nos projets](https://www.sauvegardeartfrancais.fr/nos-projets/)")
        )

    def test_lien_vide(self):
        self.assertTrue(is_noise_line("[ ](https://www.sauvegardeartfrancais.fr/)"))

    def test_bandeau_cookies_et_chrome(self):
        self.assertTrue(is_noise_line("Nous utilisons des cookies pour améliorer votre visite"))
        self.assertTrue(is_noise_line("[Mot de passe oublié ?](https://exemple.fr/lostpassword)"))
        self.assertTrue(is_noise_line("Se connecter"))

    def test_separateurs_et_images(self):
        self.assertTrue(is_noise_line("* * *"))
        self.assertTrue(is_noise_line("![](https://exemple.fr/logo.png)"))
        self.assertTrue(is_noise_line("   "))

    def test_prose_conservee(self):
        self.assertFalse(is_noise_line("Les travaux doivent concerner le gros œuvre."))
        self.assertFalse(is_noise_line("## Demander une aide"))

    def test_lien_porteur_de_chiffre_conserve(self):
        # Garde-fou : une échéance annoncée dans un libellé de lien est
        # précisément le changement que la veille doit détecter.
        self.assertFalse(is_noise_line("[Règlement 2026](https://exemple.fr/reglement.pdf)"))
        self.assertFalse(is_noise_line("* [Dépôt jusqu'au 15 novembre](https://exemple.fr/depot)"))

    def test_lien_a_libelle_long_conserve(self):
        long_label = "Consulter la liste des pièces à joindre à votre dossier de candidature"
        self.assertFalse(is_noise_line(f"[{long_label}](https://exemple.fr/pieces)"))


class TestFindQuote(unittest.TestCase):
    def test_correspondance_exacte(self):
        hay = "Nous aidons à sauver en priorité les édifices qui présentent :"
        m = find_quote("en priorité les édifices", hay)
        self.assertEqual(m.status, "exacte")
        self.assertEqual(m.excerpt(hay), "en priorité les édifices")

    def test_correspondance_degradee_sur_apostrophe(self):
        # Cas réel : la quote YAML a une apostrophe droite, la page une courbe.
        hay = "à l’exclusion des travaux de peinture, de menuiserie"
        m = find_quote("à l'exclusion des travaux de peinture", hay)
        self.assertEqual(m.status, "degradee")
        # L'extrait rendu est celui de la SOURCE, typographie d'origine comprise.
        self.assertEqual(m.excerpt(hay), "à l’exclusion des travaux de peinture")

    def test_correspondance_degradee_sur_quote_repliee(self):
        quote = (
            "Les travaux doivent concerner le gros œuvre : structure de charpente, "
            "couverture et maçonnerie"
        )
        hay = (
            "## Conditions\n\nLes travaux doivent concerner le gros œuvre : structure\n"
            "de charpente, couverture et maçonnerie à l’exclusion des travaux\n"
        )
        m = find_quote(quote, hay)
        self.assertEqual(m.status, "degradee")
        self.assertIn("maçonnerie", m.excerpt(hay) or "")

    def test_quote_desaccentuee_par_pdftotext(self):
        m = find_quote("édifices antérieurs à 1800", "des edifices anterieurs a 1800, non classes")
        self.assertEqual(m.status, "degradee")

    def test_absente(self):
        m = find_quote(
            "plafond de 50 000 €", "Les dossiers reçoivent une aide de 5 000 € en moyenne"
        )
        self.assertEqual(m.status, "absente")
        self.assertFalse(m.found)

    def test_prefixe_diagnostique_localise_la_divergence(self):
        # Distingue une vraie disparition d'une divergence de fin de phrase :
        # c'est ce qui permet de trier la dette de quotes sans relire la source.
        hay = "Les dossiers sélectionnés recevront une aide de 3 000 € en moyenne."
        m = find_quote("Les dossiers sélectionnés recevront une aide de 5 000 €", hay)
        self.assertEqual(m.status, "absente")
        self.assertGreater(m.prefix_ratio, 0.5)

        # A contrario, une condition réellement disparue ne partage qu'un début
        # fortuit (ici « un », présent dans « une aide ») : le ratio l'isole.
        disparue = find_quote("Un architecte du patrimoine est obligatoire", hay)
        self.assertLess(disparue.prefix_ratio, 0.1)

    def test_pdf_qualifie_la_provenance(self):
        m = find_quote("antérieurs à 1800", "édifices antérieurs à 1800", source_kind="pdf")
        self.assertEqual(m.status, "baseline_pdf")
        # Une absence reste une absence, quelle que soit la provenance.
        self.assertEqual(find_quote("absent", "texte", source_kind="pdf").status, "absente")

    def test_quote_vide_est_absente(self):
        self.assertEqual(find_quote("", "du texte").status, "absente")
        self.assertEqual(find_quote("   ", "du texte").status, "absente")


class TestElision(unittest.TestCase):
    """Les quotes du dépôt utilisent « ... » pour sauter un passage.

    C'est une convention de saisie, pas un caractère de la source : la chercher
    littéralement fait échouer des citations authentiques. Mesuré sur les 142
    aides, c'est la deuxième cause de fausses absences après l'espace
    typographique.
    """

    SOURCE = (
        "Le bénéficiaire s'engage à apposer le logo du Conseil départemental sur "
        "l'ensemble des documents d'informations (courriers, affiches, dossiers "
        "de presse) relatifs à ce partenariat. Un exemplaire sera transmis au "
        "Département avant diffusion."
    )

    def test_elision_interne_reconstituee(self):
        quote = "documents d'informations ... relatifs à ce partenariat."
        m = find_quote(quote, self.SOURCE)
        self.assertEqual(m.status, "degradee")
        self.assertEqual(m.reconstitution, "elision")
        # Le span couvre les deux fragments et ce qui a été sauté entre eux.
        self.assertIn("(courriers", m.excerpt(self.SOURCE) or "")

    def test_elision_finale_de_troncature(self):
        m = find_quote("l'ensemble des documents d'informations...", self.SOURCE)
        self.assertEqual(m.status, "degradee")
        self.assertEqual(m.reconstitution, "elision")

    def test_fragments_dans_le_desordre_refuses(self):
        m = find_quote("relatifs à ce partenariat ... documents d'informations", self.SOURCE)
        self.assertEqual(m.status, "absente")

    def test_fragment_absent_refuse(self):
        m = find_quote("documents d'informations ... un architecte du patrimoine", self.SOURCE)
        self.assertEqual(m.status, "absente")

    def test_miettes_sans_ancrage_refusees(self):
        # Une quote réduite à de la ponctuation matcherait n'importe quoi.
        self.assertEqual(find_quote(": ... ). ... ,", self.SOURCE).status, "absente")

    def test_fenetre_bornee(self):
        # Deux fragments authentiques mais séparés par tout un règlement ne
        # constituent pas une citation : une élision saute une incise.
        loin = "Premier fragment cité." + (" remplissage." * 300) + " Second fragment cité."
        self.assertEqual(
            find_quote("Premier fragment cité. ... Second fragment cité.", loin).status,
            "absente",
        )

    def test_citation_contigue_prime_l_elision(self):
        # Cas réel (77-equipements-culturels) : les formulaires contiennent de
        # vrais « ... » à remplir. Quand une même quote matche littéralement
        # dans un document et par élision dans un autre, c'est le littéral qui
        # doit gagner — sinon le rapport désigne la mauvaise source.
        quote = "une subvention d'un montant de : ...€"
        docs = [
            ("elision.md", "une subvention d'un montant de : cliquez ici pour 20 €", "text"),
            ("formulaire.md", "attribué une subvention d'un montant de : ...€ pour 2026", "text"),
        ]
        name, match = find_quote_in_any(quote, docs)
        self.assertEqual(name, "formulaire.md")
        self.assertIsNone(match.reconstitution)


class TestPonctuationFinale(unittest.TestCase):
    """Citer une longue phrase en la coupant la clôt par un point que la source
    n'a pas à cet endroit. Mesuré sur les 142 aides : première cause de quotes
    authentiques encore déclarées absentes après normalisation.
    """

    def test_point_de_cloture_ajoute_a_la_saisie(self):
        # Cas réel (idf-restauration-maisons-artistes/taux-40) : la source
        # continue la phrase, la quote la referme.
        source = (
            "appliqué au coût des travaux et aux honoraires de maîtrise d'œuvre, "
            "à l'exclusion des postes de dépenses suivants"
        )
        m = find_quote(
            "appliqué au coût des travaux et aux honoraires de maîtrise d'œuvre.", source
        )
        self.assertEqual(m.status, "degradee")
        self.assertEqual(m.reconstitution, "ponctuation_finale")

    def test_appel_de_note_colle_par_pdftotext(self):
        # Cas réel (aura-festivals/plafond-50-budget) : « prévisionnel2. »
        source = "Le financement régional ne pourra pas dépasser 50% du budget prévisionnel2."
        m = find_quote(
            "Le financement régional ne pourra pas dépasser 50% du budget prévisionnel.", source
        )
        self.assertEqual(m.reconstitution, "ponctuation_finale")

    def test_parenthese_de_cloture(self):
        # Cas réel (cd43-mh-publics/taux-objets-2016) : « de 10%1). »
        source = "ramené à 20 %, si le Conseil régional intervient à hauteur de 10%1)."
        m = find_quote(
            "ramené à 20 %, si le Conseil régional intervient à hauteur de 10%).", source
        )
        self.assertEqual(m.reconstitution, "ponctuation_finale")

    def test_retouche_refusee_si_elle_ampute_la_substance(self):
        # Une quote presque entièrement faite de ponctuation ne doit pas devenir
        # une preuve : le garde-fou porte sur ce qui RESTE après retouche.
        self.assertEqual(find_quote("40 %.", "un taux de 40 % maximum").status, "absente")

    def test_divergence_reelle_reste_absente(self):
        # Le rabotage ne touche QUE la fin : un chiffre changé reste une absence.
        source = "Le financement régional ne pourra pas dépasser 80% du budget prévisionnel."
        m = find_quote(
            "Le financement régional ne pourra pas dépasser 50% du budget prévisionnel.", source
        )
        self.assertEqual(m.status, "absente")

    def test_citation_intacte_prime_la_retouche(self):
        quote = "aux honoraires de maîtrise d'œuvre du projet."
        docs = [
            ("retouche.md", "aux honoraires de maîtrise d'œuvre du projet, hors taxes", "text"),
            ("intacte.md", "aux honoraires de maîtrise d'œuvre du projet. Le taux est de", "text"),
        ]
        name, match = find_quote_in_any(quote, docs)
        self.assertEqual(name, "intacte.md")
        self.assertIsNone(match.reconstitution)


class TestFlattenMarkdownLinks(unittest.TestCase):
    def test_lien_en_milieu_de_phrase(self):
        # Cas réel (aides Île-de-France) : html2text enrobe une ancre au milieu
        # d'une phrase, ce qui casse une quote saisie depuis le rendu visuel.
        md = "déposer une offre sur la plateforme [stages.iledefrance.fr](https://stages.iledefrance.fr)"
        self.assertEqual(
            flatten_markdown_links(md),
            "déposer une offre sur la plateforme stages.iledefrance.fr",
        )

    def test_quote_retrouvee_apres_aplatissement(self):
        md = "sur la plateforme [mesdemarches.fr](https://mesdemarches.iledefrance.fr/aides)"
        quote = "sur la plateforme mesdemarches.fr"
        self.assertEqual(find_quote(quote, md).status, "absente")
        self.assertTrue(find_quote(quote, flatten_markdown_links(md)).found)

    def test_libelle_conserve_caractere_pour_caractere(self):
        md = "[Règlement d'intervention 2026 — patrimoine](https://exemple.fr/r.pdf)"
        self.assertEqual(flatten_markdown_links(md), "Règlement d'intervention 2026 — patrimoine")

    def test_url_parenthesee_geree(self):
        md = "voir [la notice](https://exemple.fr/notice_(v2).pdf) pour le détail"
        self.assertEqual(flatten_markdown_links(md), "voir la notice pour le détail")

    def test_texte_sans_lien_intact(self):
        prose = "Les travaux doivent concerner le gros œuvre (charpente, couverture)."
        self.assertEqual(flatten_markdown_links(prose), prose)


class TestFindQuoteInAny(unittest.TestCase):
    DOCS = [
        ("page.md", "Menu — nos projets, la fondation.", "text"),
        ("reglement.pdf", "des edifices anterieurs a 1800, non classes", "pdf"),
        ("criteres.md", "Les édifices antérieurs à 1800 sont éligibles.", "text"),
    ]

    def test_garde_la_meilleure_preuve_pas_la_premiere(self):
        # La quote est justifiée par le PDF ET par la page : c'est la preuve la
        # plus forte qui doit ressortir, pas celle du premier document essayé.
        name, match = find_quote_in_any("antérieurs à 1800", self.DOCS)
        self.assertEqual(name, "criteres.md")
        self.assertEqual(match.status, "exacte")

    def test_repli_sur_le_pdf_quand_seul_a_justifier(self):
        name, match = find_quote_in_any("non classés", self.DOCS)
        self.assertEqual(name, "reglement.pdf")
        self.assertEqual(match.status, "baseline_pdf")

    def test_introuvable_partout(self):
        name, match = find_quote_in_any("plafond de 50 000 €", self.DOCS)
        self.assertIsNone(name)
        self.assertEqual(match.status, "absente")

    def test_aucun_document(self):
        name, match = find_quote_in_any("antérieurs à 1800", [])
        self.assertIsNone(name)
        self.assertEqual(match.status, "absente")


class TestNormalizedDiff(unittest.TestCase):
    PAGE = (
        "# Demander une aide\n"
        "\n"
        "  * [Nos projets](https://exemple.fr/nos-projets/)\n"
        "  * [Mon compte](https://exemple.fr/mon-compte/)\n"
        "\n"
        "Les édifices doivent être antérieurs à 1800.\n"
        "Les dossiers sélectionnés recevront une aide de 5 000 € en moyenne.\n"
    )

    def test_bruit_typographique_seul_donne_un_diff_vide(self):
        # Le gold « sauvegarde-art-francais » : la page a changé de sha sans
        # changer de fond. Un diff non vide ici enverrait une aide au LLM pour rien.
        cosmetique = (
            self.PAGE.replace("antérieurs à 1800", "antérieurs à 1800")
            .replace("être", "être")
            .replace("5 000 €", "5 000 €")
        )
        diff = normalized_diff(self.PAGE, cosmetique)
        self.assertTrue(diff.is_empty)
        self.assertEqual(diff.ratio, 0.0)

    def test_document_identique(self):
        diff = normalized_diff(self.PAGE, self.PAGE)
        self.assertTrue(diff.is_empty)

    def test_changement_de_fond_detecte_et_affiche_en_brut(self):
        modifie = self.PAGE.replace("5 000 €", "8 000 €")
        diff = normalized_diff(self.PAGE, modifie)
        self.assertFalse(diff.is_empty)
        self.assertEqual((diff.removed, diff.added), (1, 1))
        # Le diff s'aligne sur le normalisé mais s'affiche en texte brut :
        # accents et casse conservés, pour le rapport et pour le prompt.
        self.assertIn(
            "- Les dossiers sélectionnés recevront une aide de 5 000 € en moyenne.", diff.text
        )
        self.assertIn(
            "+ Les dossiers sélectionnés recevront une aide de 8 000 € en moyenne.", diff.text
        )

    def test_menu_change_sans_declencher_de_diff(self):
        avec_menu = self.PAGE.replace(
            "  * [Mon compte](https://exemple.fr/mon-compte/)",
            "  * [Espace personnel](https://exemple.fr/espace/)\n"
            "  * [Nous soutenir](https://exemple.fr/dons/)",
        )
        diff = normalized_diff(self.PAGE, avec_menu)
        self.assertTrue(diff.is_empty)
        self.assertGreater(diff.noise_filtered, 0)

    def test_ratio_borne_l_escalade(self):
        diff = normalized_diff(self.PAGE, "# Page refondue\n\nRien à voir avec l'ancienne.\n")
        self.assertGreater(diff.ratio, 0.5)

    def test_ratio_juste_meme_quand_le_texte_est_tronque(self):
        # Un plafond d'AFFICHAGE ne doit pas fausser une décision d'escalade.
        old = "\n".join(f"Ligne de contenu numéro {i}." for i in range(100))
        new = "\n".join(f"Autre contenu numéro {i}." for i in range(100))
        diff = normalized_diff(old, new, max_lines=10)
        self.assertTrue(diff.truncated)
        self.assertEqual(diff.changed, 200)
        self.assertEqual(diff.ratio, 2.0)
        self.assertIn("omise(s)", diff.text)

    def test_documents_vides(self):
        self.assertTrue(normalized_diff("", "").is_empty)
        self.assertFalse(normalized_diff("", "Nouveau contenu.").is_empty)


class TestIsCosmeticChange(unittest.TestCase):
    def test_typographie_seule(self):
        self.assertTrue(is_cosmetic_change("l'édifice", "l’édifice"))
        self.assertTrue(is_cosmetic_change("80 %", "80 %"))
        self.assertTrue(is_cosmetic_change("gros œuvre\ncharpente", "gros oeuvre charpente"))

    def test_changement_reel(self):
        self.assertFalse(is_cosmetic_change("5 000 €", "8 000 €"))
        self.assertFalse(is_cosmetic_change("antérieurs à 1800", "antérieurs à 1850"))

    def test_none_et_vide_equivalents(self):
        self.assertTrue(is_cosmetic_change(None, ""))
        self.assertTrue(is_cosmetic_change(None, "  \n "))
        self.assertFalse(is_cosmetic_change(None, "une note ajoutée"))


class TestBruitDesPortails(unittest.TestCase):
    """Les deux fausses alertes de la garde au banc Jev du 2026-10-04 (savoie.fr)."""

    def test_jeton_de_session_est_du_bruit(self):
        self.assertTrue(
            is_noise_line("eNq9mFFv2jAQx9/5FCjvJNDSdpsC1cbaDanVGC3atJfKJEcxS+30bJN0n34XQ")
        )
        # Le bout de jeton coupé en fin de ligne aussi.
        self.assertTrue(is_noise_line("30vXeQ1Nej0HQKqw"))

    def test_mot_de_reglement_n_est_pas_un_jeton(self):
        for ligne in ("Auvergne-Rhone-Alpes", "COVID-19", "2026-2027", "SIRET"):
            self.assertFalse(is_noise_line(ligne), ligne)

    def test_ligne_deplacee_n_est_pas_un_changement(self):
        avant = (
            "Intro du dispositif.\nPlafond à 500 000 € maximum.\nBénéficiaires : communes.\nFin."
        )
        apres = (
            "Intro du dispositif.\nBénéficiaires : communes.\nPlafond à 500 000 € maximum.\nFin."
        )
        d = normalized_diff(avant, apres)
        self.assertTrue(d.is_empty, d.text)

    def test_deplacement_et_vrai_changement(self):
        avant = "A.\nPlafond à 500 000 €.\nB.\nDate limite : 30 septembre 2026."
        apres = "A.\nB.\nPlafond à 500 000 €.\nDate limite : 30 octobre 2026."
        d = normalized_diff(avant, apres)
        self.assertEqual((d.added, d.removed), (1, 1))
        self.assertIn("+ Date limite : 30 octobre 2026.", d.text)
        self.assertNotIn("500 000", d.text)


if __name__ == "__main__":
    unittest.main()
