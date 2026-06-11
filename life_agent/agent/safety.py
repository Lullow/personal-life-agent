"""Safety rules governing how natural language input may affect the database.

The core rule for this project is simple and strict:

    Natural language input must not write to the database without explicit
    user confirmation.

The ``extract`` command is always read-only.  The ``add`` command may only
persist extracted items *after* the user has explicitly confirmed the
proposal.  These helpers centralise that policy so callers cannot bypass it
by accident.
"""

CONFIRMATION_REQUIRED_RULE = (
    "Natural language input must not write to the database without explicit "
    "confirmation."
)

# Answers that count as an explicit "yes".
_AFFIRMATIVE_ANSWERS = {"y", "yes", "j", "ja"}


def is_affirmative(answer: str | None) -> bool:
    """Return *True* only for an explicit affirmative answer.

    Anything else — including ``None``, an empty string (a bare Enter), or
    ``n``/``no`` — is treated as a refusal, so the default is always "do not
    save".
    """
    if answer is None:
        return False
    return answer.strip().lower() in _AFFIRMATIVE_ANSWERS


def assert_confirmed(confirmed: bool) -> None:
    """Guard used before any natural-language-driven write.

    Raises :class:`PermissionError` if called without an explicit
    confirmation, enforcing :data:`CONFIRMATION_REQUIRED_RULE`.
    """
    if not confirmed:
        raise PermissionError(CONFIRMATION_REQUIRED_RULE)
