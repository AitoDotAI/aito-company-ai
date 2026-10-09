"""What "now" the READS reckon from.

A fixed demo dataset rots: its newest row recedes from today until every deal
reads as stalled and every todo as overdue, which makes the Now view's ranking
say nothing and the product look neglected rather than quiet.

Two ways to stop that. Move the data toward today, which drifts — reseed on a
Monday and on a Friday and you get different numbers, the instance stops
matching `data/seed/`, and every screenshot in `docs/` ages out. Or declare the
date the dataset reckons from, the way a balance sheet says "as at 31
December". This module is the second one.

It is deliberately narrow:

  * READS only. `created`, `ts`, `last_done` and every other write stamp keeps
    the real clock, so the changelog and the audit trail cannot be back-dated.
  * OFF unless configured. Unset means `date.today()`, so a live instance
    cannot drift into it by accident.
  * never silent. Whenever it is set, the API reports it and the UI shows it.
    An instance quietly reckoning from a date that is not today is exactly the
    dishonesty this exists to avoid.
"""

from datetime import date

from .config import SEED_DIR, Config


def reckoning() -> date | None:
    """The configured as-of date, or None when the real clock is in use.

    A PUBLIC DEMO serves the shipped synthetic seed by definition (it refuses
    the internal instance, docs/33), and has no `./do seed` to record the seed's
    date — it runs in a container. So unless COMPANY_AI_AS_OF says otherwise it
    reckons from the seed's own anchor (data/seed/AS_OF); without that, every
    visitor would see a pipeline where every deal is stalled. The banner shows
    it either way."""
    config = Config.from_env()
    if config.as_of:
        return config.as_of
    anchor = SEED_DIR / "AS_OF"
    if config.public_demo and anchor.exists():
        return date.fromisoformat(anchor.read_text().strip())
    return None


def today() -> date:
    """The date reads compare against: the configured as-of, else the real one."""
    return reckoning() or date.today()
