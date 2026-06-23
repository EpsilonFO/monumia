-- Seed the Aveyron departmental fund for restoration of non-protected rural heritage.
-- Source: aveyron.csv export.
insert into public.aides_v3 (
    id,
    nom,
    nom_court,
    description,
    description_longue,
    categorie,
    type,
    organisme,
    montant_max,
    taux_max,
    montant_min,
    plancher,
    base_ttc,
    commune_max_population,
    cofinancement_requis,
    architecte_requis,
    conditions_eligibilite_detail,
    demarche_description,
    documents_requis,
    delai_instruction,
    date_ouverture,
    date_limite,
    permanent,
    url_officielle,
    formulaire_url,
    created_at,
    updated_at,
    source_at_slug
) values (
    '42388640-5808-4f34-9223-92a29806429b',
    'Fonds Départemental de Soutien à la Restauration du Patrimoine Rural Non Protégé',
    'Fonds départemental de l''Aveyron',
    'test',
    null,
    'departement',
    'subvention',
    'Conseil départemental de l''Aveyron — Direction de la culture, du patrimoine et de la lecture publique',
    12000,
    30,
    null,
    null,
    false,
    null,
    false,
    false,
    null,
    null,
    '[
        "Lettre de saisine à adresser à Monsieur le Président du Département",
        "Délibération approuvant le projet et le plan de financement (collectivités locales)",
        "Plan de financement prévisionnel (propriétaires privés et associations)",
        "Notice explicative, programme détaillé des travaux, dossier avant-projet s''il y a lieu",
        "Résultat de la consultation des entreprises, devis",
        "Plans de localisation cadastral",
        "Photos"
    ]'::jsonb,
    null,
    null,
    null,
    true,
    'https://aveyron.fr/pages/soutien-a-la-restauration-du-patrimoine-rural-non-protege/fonds-departemental-de-soutien-au-patrimoine',
    null,
    '2026-05-15 09:03:06.834083+00',
    '2026-05-15 09:03:06.834083+00',
    null
)
on conflict (id) do nothing;

-- Link the aid to the Aveyron department (INSEE code 12).
insert into public.aides_departements (aide_id, departement_code)
values ('42388640-5808-4f34-9223-92a29806429b', '12')
on conflict (aide_id, departement_code) do nothing;
