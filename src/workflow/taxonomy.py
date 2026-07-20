"""Approved taxonomy synchronization and review helpers."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.shared.models import Category, Subcategory, Topic


def sync_taxonomy_catalog(session: Session, catalog_path: Path) -> int:
    """Add approved catalog labels without deleting or renaming database records."""
    if not catalog_path.exists():
        return 0

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    existing = {name.casefold() for name in session.scalars(select(Category.name))}
    added = 0

    for entry in catalog.get("categories", []):
        name = str(entry.get("name", "")).strip()
        if not name or name.casefold() in existing:
            continue
        session.add(Category(name=name, is_active=True))
        existing.add(name.casefold())
        added += 1

    if added:
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
