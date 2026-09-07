from __future__ import annotations

import csv
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DatasetLabel, Image

MANIFEST_COLUMNS = {"image_id", "file_path", "dataset_label", "source_url", "license_url"}
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class ManifestValidationError(ValueError):
    """Raised when a corpus manifest is incomplete or unsafe to import."""


@dataclass(frozen=True)
class CorpusManifestRow:
    image_id: uuid.UUID
    file_path: str
    dataset_label: DatasetLabel
    source_url: str
    license_url: str
    absolute_path: Path


@dataclass(frozen=True)
class CorpusImportSummary:
    created: int
    skipped: int


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as image_file:
        while chunk := image_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(manifest_path: Path, project_root: Path) -> list[CorpusManifestRow]:
    if not manifest_path.is_file():
        raise ManifestValidationError(f"Manifest file does not exist: {manifest_path}")

    corpus_root = (project_root / "data" / "corpus" / "raw").resolve()
    rows: list[CorpusManifestRow] = []
    seen_ids: set[uuid.UUID] = set()
    seen_paths: set[str] = set()

    with manifest_path.open("r", encoding="utf-8", newline="") as manifest_file:
        reader = csv.DictReader(manifest_file)
        field_names = set(reader.fieldnames or [])
        if field_names != MANIFEST_COLUMNS:
            raise ManifestValidationError(
                "Manifest columns must be: image_id, file_path, dataset_label, "
                "source_url, license_url"
            )

        for line_number, raw_row in enumerate(reader, start=2):
            rows.append(
                _parse_manifest_row(
                    raw_row=raw_row,
                    line_number=line_number,
                    project_root=project_root,
                    corpus_root=corpus_root,
                    seen_ids=seen_ids,
                    seen_paths=seen_paths,
                )
            )

    if not rows:
        raise ManifestValidationError("Manifest must contain at least one image row")
    return rows


def import_manifest(session: Session, rows: list[CorpusManifestRow]) -> CorpusImportSummary:
    created = 0
    skipped = 0

    for row in rows:
        checksum = compute_sha256(row.absolute_path)
        image_by_id = session.get(Image, row.image_id)
        image_by_path = session.scalar(select(Image).where(Image.file_path == row.file_path))
        image_by_checksum = session.scalar(select(Image).where(Image.sha256 == checksum))
        existing_images = [
            image for image in (image_by_id, image_by_path, image_by_checksum) if image
        ]

        if not existing_images:
            session.add(
                Image(
                    id=row.image_id,
                    file_path=row.file_path,
                    sha256=checksum,
                    dataset_label=row.dataset_label,
                    source_url=row.source_url,
                    license_url=row.license_url,
                )
            )
            created += 1
            continue

        if len({image.id for image in existing_images}) != 1:
            raise ManifestValidationError(
                f"Manifest image {row.file_path} conflicts with an existing path, checksum, or ID"
            )

        existing_image = existing_images[0]
        if not _matches_existing_image(existing_image, row, checksum):
            raise ManifestValidationError(
                f"Manifest image {row.file_path} conflicts with existing image {existing_image.id}"
            )
        skipped += 1

    return CorpusImportSummary(created=created, skipped=skipped)


def _parse_manifest_row(
    raw_row: dict[str, str | None],
    line_number: int,
    project_root: Path,
    corpus_root: Path,
    seen_ids: set[uuid.UUID],
    seen_paths: set[str],
) -> CorpusManifestRow:
    values = {name: (raw_row.get(name) or "").strip() for name in MANIFEST_COLUMNS}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ManifestValidationError(
            f"Manifest line {line_number} is missing: {', '.join(missing)}"
        )

    try:
        image_id = uuid.UUID(values["image_id"])
    except ValueError as error:
        raise ManifestValidationError(
            f"Manifest line {line_number} has an invalid image_id"
        ) from error
    if image_id in seen_ids:
        raise ManifestValidationError(f"Manifest line {line_number} repeats image_id {image_id}")
    seen_ids.add(image_id)

    try:
        dataset_label = DatasetLabel(values["dataset_label"])
    except ValueError as error:
        raise ManifestValidationError(
            f"Manifest line {line_number} has an unsupported dataset_label"
        ) from error

    file_path = Path(values["file_path"])
    if file_path.is_absolute():
        raise ManifestValidationError(f"Manifest line {line_number} must use a relative file_path")
    absolute_path = (project_root / file_path).resolve()
    if not absolute_path.is_relative_to(corpus_root):
        raise ManifestValidationError(f"Manifest line {line_number} points outside data/corpus/raw")
    if absolute_path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES or not absolute_path.is_file():
        raise ManifestValidationError(
            f"Manifest line {line_number} points to a missing or unsupported image"
        )
    if absolute_path.parent.name != dataset_label.value:
        raise ManifestValidationError(
            f"Manifest line {line_number} label does not match its corpus directory"
        )

    normalized_path = file_path.as_posix()
    if normalized_path in seen_paths:
        raise ManifestValidationError(
            f"Manifest line {line_number} repeats file_path {normalized_path}"
        )
    seen_paths.add(normalized_path)

    _require_http_url(values["source_url"], line_number, "source_url")
    _require_http_url(values["license_url"], line_number, "license_url")

    return CorpusManifestRow(
        image_id=image_id,
        file_path=normalized_path,
        dataset_label=dataset_label,
        source_url=values["source_url"],
        license_url=values["license_url"],
        absolute_path=absolute_path,
    )


def _matches_existing_image(image: Image, row: CorpusManifestRow, checksum: str) -> bool:
    return (
        image.id == row.image_id
        and image.file_path == row.file_path
        and image.sha256 == checksum
        and image.dataset_label == row.dataset_label
        and image.source_url == row.source_url
        and image.license_url == row.license_url
    )


def _require_http_url(value: str, line_number: int, field_name: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ManifestValidationError(f"Manifest line {line_number} has an invalid {field_name}")
