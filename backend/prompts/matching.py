from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_prompts_dir = Path(__file__).parent
_jinja_env = Environment(loader=FileSystemLoader(_prompts_dir), keep_trailing_newline=True)


def render_prompt_eligibility(
    monument_profile: str,
    aide_nom: str,
    bullets: list[str],
) -> str:
    """Render the eligibility evaluation prompt from the Jinja2 template.

    The prompt asks the LLM to emit one verdict per bullet (oui/non/incertitude).
    """
    template = _jinja_env.get_template("eligibility.j2")
    return template.render(
        monument_profile=monument_profile,
        aide_nom=aide_nom,
        bullets=bullets,
    )


def render_prompt_qcm(
    max_questions: int,
    monument_profile: str,
    incertitudes_json: str,
) -> str:
    """Render the QCM prompt from the Jinja2 template."""
    template = _jinja_env.get_template("qcm.j2")
    return template.render(
        max_questions=max_questions,
        monument_profile=monument_profile,
        incertitudes_json=incertitudes_json,
    )
