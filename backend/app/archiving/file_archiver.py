"""
Archives a copy of every uploaded raw file into:

  {archive_root}/tunisie/{gouvernorat}/{delegation}/{secteur}/{type_de_test}/{technologie}/

Per the agreed policy: one file -> filed under the SECTOR CONTAINING THE
MAJORITY of its points (not split per-sector). DB rows keep their own
accurate per-row secteur_id regardless of where the raw file physically
lives, so no analytical accuracy is lost - this only affects the on-disk
backup copy's location.
"""
import logging
import re
import shutil
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def _sanitize_path_component(name: str) -> str:
    """Filesystem-safe folder name (handles French accents, spaces, slashes)."""
    name = name.strip().replace("/", "-").replace("\\", "-")
    name = re.sub(r"[^\w\-. ]", "_", name, flags=re.UNICODE)
    return name or "unknown"


def build_archive_path(gouvernorat: str, delegation: str, secteur: str,
                        type_de_test: str, technologie: str | None) -> Path:
    technologie = technologie or "unknown_tech"
    return (
        settings.archive_root
        / "tunisie"
        / _sanitize_path_component(gouvernorat)
        / _sanitize_path_component(delegation)
        / _sanitize_path_component(secteur)
        / _sanitize_path_component(type_de_test)
        / _sanitize_path_component(technologie)
    )


def archive_file(source_path: Path, gouvernorat: str, delegation: str, secteur: str,
                  type_de_test: str, technologie: str | None, original_filename: str) -> str:
    """
    Copies source_path into the resolved sector folder. Returns the final
    archive path as a string (stored on UploadedFile.archive_path for the
    admin "delete by log file path" feature).
    """
    target_dir = build_archive_path(gouvernorat, delegation, secteur, type_de_test, technologie)
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / original_filename
    # Avoid silently overwriting a same-named previous upload
    if target_path.exists():
        stem, suffix = target_path.stem, target_path.suffix
        i = 1
        while target_path.exists():
            target_path = target_dir / f"{stem}__{i}{suffix}"
            i += 1

    shutil.copy2(source_path, target_path)
    logger.info("Archived %s -> %s", original_filename, target_path)
    return str(target_path)


def delete_archived_file(archive_path: str) -> bool:
    """Used by the Admin 'delete by log file path' feature."""
    p = Path(archive_path)
    if p.exists():
        p.unlink()
        logger.info("Deleted archived file %s", archive_path)
        return True
    logger.warning("Archived file not found for deletion: %s", archive_path)
    return False
