from __future__ import annotations

from app.db.session import SessionLocal
from app.services.embedding_costs import print_embedding_costs


def main() -> int:
    with SessionLocal() as session:
        print_embedding_costs(session)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
