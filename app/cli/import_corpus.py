from __future__ import annotations

import argparse
from pathlib import Path

from app.db.session import SessionLocal
from app.services.corpus import ManifestValidationError, import_manifest, load_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Register corpus images from a provenance manifest."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/corpus/manifest.csv"),
        help="Path to the corpus manifest, relative to the project root.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root containing data/corpus/raw.",
    )
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = build_parser().parse_args(arguments)
    project_root = args.project_root.resolve()
    manifest_path = (project_root / args.manifest).resolve()

    try:
        rows = load_manifest(manifest_path, project_root)
        with SessionLocal() as session:
            summary = import_manifest(session, rows)
            session.commit()
    except ManifestValidationError as error:
        print(f"Corpus import failed: {error}")
        return 1

    print(f"Corpus import complete: created={summary.created}, skipped={summary.skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
