-- Persist QCM state on diagnostics so the post-QCM filter survives a page reload.
--   qcm_answers       : { question_id: option_id } chosen by the user
--   llm_evaluations   : { aide_id: { explication, incertitudes: [{categorie, detail}, …] } }
--                       captured at diagnostic time so the frontend can re-mark
--                       clarified incertitudes without re-running the LLM.

alter table public.diagnostics
  add column if not exists qcm_answers     jsonb not null default '{}'::jsonb,
  add column if not exists llm_evaluations jsonb not null default '{}'::jsonb;
