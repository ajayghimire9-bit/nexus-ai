"""Record that vague authorization is insufficient. Not science."""
from __future__ import annotations

import sys

from nexus.evolution2.persist_reset_approval import write_artifact


def main(argv: list[str] | None = None) -> None:
    text = " ".join(sys.argv[1:] if argv is None else argv) or "continue i authrosed you"
    payload = write_artifact(text)
    print(payload["parsed"]["status"], payload["parsed"]["missing"])


if __name__ == "__main__":
    main()
