"""zh-copy-lint: lint Chinese copy for typography problems."""

from .rules import Issue, fix_text, lint_text

__all__ = ["Issue", "fix_text", "lint_text", "__version__"]
__version__ = "0.1.0"
