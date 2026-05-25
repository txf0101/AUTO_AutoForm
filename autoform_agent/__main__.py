"""Module entry point for `python -m autoform_agent`.

Keeping this file small makes the command-line package behavior easy to audit:
all argument parsing and command dispatch lives in `autoform_agent.cli.main`.
"""

from .cli import main


if __name__ == "__main__":
    # Convert the integer return value from `main` into the process exit status.
    raise SystemExit(main())
