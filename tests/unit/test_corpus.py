from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest

from app.db.models import DatasetLabel
from app.services.corpus import ManifestValidationError, compute_sha256, load_manifest


def write_manifest(
    project_root: Path, source_url: str = "https://images.pexels.com/example"
) -> Path:
    image_path = project_root / "data/corpus/raw/red_fox/red_fox_001.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image-content")
    manifest_path = project_root / "data/corpus/manifest.csv"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "image_id,file_path,dataset_label,source_url,license_url\n"
        f"{uuid.uuid4()},data/corpus/raw/red_fox/red_fox_001.jpg,red_fox,{source_url},"
        "https://www.pexels.com/license/\n",
        encoding="utf-8",
    )
    return manifest_path


def test_load_manifest_validates_provenance_and_image_path(tmp_path: Path) -> None:
    manifest_path = write_manifest(tmp_path)

    rows = load_manifest(manifest_path, tmp_path)

    assert len(rows) == 1
    assert rows[0].dataset_label == DatasetLabel.RED_FOX
    assert rows[0].file_path == "data/corpus/raw/red_fox/red_fox_001.jpg"


def test_load_manifest_rejects_missing_or_invalid_provenance(tmp_path: Path) -> None:
    manifest_path = write_manifest(tmp_path, source_url="not-a-url")

    with pytest.raises(ManifestValidationError, match="invalid source_url"):
        load_manifest(manifest_path, tmp_path)


def test_compute_sha256_uses_file_contents(tmp_path: Path) -> None:
    image_path = tmp_path / "image.jpg"
    image_path.write_bytes(b"image-content")

    assert compute_sha256(image_path) == hashlib.sha256(b"image-content").hexdigest()
