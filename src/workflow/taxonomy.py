"""Approved taxonomy synchronization and review helpers."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.shared.models import Category, Subcategory, Topic

EXCLUDED_CATEGORY_NAMES = {"informational only"}
CATEGORY_NAME_NORMALIZATION = {
    "ineligible player for sectionals notification": "Ineligible player",
}


def normalize_catalog_category_name(name: str) -> str | None:
    normalized = name.strip()
    if not normalized:
        return None
    if normalized.casefold() in EXCLUDED_CATEGORY_NAMES:
        return None
    return CATEGORY_NAME_NORMALIZATION.get(normalized.casefold(), normalized)


def sync_taxonomy_catalog(session: Session, catalog_path: Path) -> int:
    """Add approved catalog labels and deactivate excluded legacy labels."""
    if not catalog_path.exists():
        return 0

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    existing = {name.casefold() for name in session.scalars(select(Category.name))}
    added = 0
    changed = False

    for category in session.scalars(select(Category).where(Category.is_active.is_(True))):
        if normalize_catalog_category_name(category.name) is None:
            category.is_active = False
            changed = True

    for entry in catalog.get("categories", []):
        raw_name = str(entry.get("name", ""))
        name = normalize_catalog_category_name(raw_name)
        if not name or name.casefold() in existing:
            continue
        session.add(Category(name=name, is_active=True))
        existing.add(name.casefold())
        added += 1

    if added or changed:
        session.commit()
    return added


def list_active_categories(session: Session) -> list[Category]:
    return list(session.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.name)))


def list_active_subcategories(session: Session) -> list[Subcategory]:
    return list(
        session.scalars(
            select(Subcategory).where(Subcategory.is_active.is_(True)).order_by(Subcategory.category_id, Subcategory.name)
        )
    )


def list_active_topics(session: Session) -> list[Topic]:
    return list(session.scalars(select(Topic).where(Topic.is_active.is_(True)).order_by(Topic.name)))
