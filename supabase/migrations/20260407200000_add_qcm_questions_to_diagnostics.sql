alter table "public"."diagnostics"
  add column "qcm_questions" jsonb default '[]'::jsonb;
