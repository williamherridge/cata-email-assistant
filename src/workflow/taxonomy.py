"""Approved taxonomy synchronization and review helpers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.shared.models import Category, Subcategory, Topic

EXCLUDED_CATEGORY_NAMES = {"informational only"}
CATEGORY_NAME_NORMALIZATION = {
    "ineligible player for sectionals notification": "Ineligible player",
}
CATEGORY_PROFILES = {
    "facility request": {
        "description": "Structured facility request submissions captured from Tennis Austin web forms.",
        "default_draft_behavior": "auto_ignore_candidate",
        "default_reply_needed": False,
        "default_informational_only": True,
        "priority_hint": "low",
    },
    "ineligible league player form": {
        "description": "Structured USTA Texas form submission identifying an ineligible league player.",
        "default_draft_behavior": "auto_ignore_candidate",
        "default_reply_needed": False,
        "default_informational_only": True,
        "priority_hint": "low",
    },
    "make-up match line up": {
        "description": "Structured CATA form submission that captures a make-up match lineup.",
        "default_draft_behavior": "auto_ignore_candidate",
        "default_reply_needed": False,
        "default_informational_only": True,
        "priority_hint": "low",
    },
    "make-up date form": {
        "description": "Structured CATA form submission that captures make-up match dates.",
        "default_draft_behavior": "auto_ignore_candidate",
        "default_reply_needed": False,
        "default_informational_only": True,
        "priority_hint": "low",
    },
    "team registration submission": {
        "description": "Structured CATA form submission for a new team registration that needs manual downstream processing.",
        "default_draft_behavior": "manual_registration_summary",
        "default_reply_needed": False,
        "default_informational_only": False,
        "priority_hint": "normal",
    },
}
logger = logging.getLogger(__name__)
_SYNC_STATE: dict[str, tuple[int, int]] = {}


def normalize_catalog_category_name(name: str) -> str | None:
    normalized = name.strip()
    if not normalized:
        return None
    if normalized.casefold() in EXCLUDED_CATEGORY_NAMES:
        return None
    return CATEGORY_NAME_NORMALIZATION.get(normalized.casefold(), normalized)


def apply_category_profile(category: Category) -> bool:
    profile = CATEGORY_PROFILES.get(category.name.casefold())
    if profile is None:
        return False

    changed = False
    for field_name, new_value in profile.items():
        if getattr(category, field_name) != new_value:
            setattr(category, field_name, new_value)
            changed = True
    return changed


def sync_taxonomy_catalog(session: Session, catalog_path: Path) -> int:
    """Add approved catalog labels and deactivate excluded legacy labels."""
    if not catalog_path.exists():
        return 0

    try:
        stat = catalog_path.stat()
    except OSError:
        logger.exception("Taxonomy catalog could not be inspected at %s.", catalog_path)
        return 0

    cache_key = str(catalog_path.resolve())
    state = (stat.st_mtime_ns, stat.st_size)
    if _SYNC_STATE.get(cache_key) == state:
        return 0

    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        logger.exception("Taxonomy catalog could not be loaded from %s.", catalog_path)
        return 0
    existing = {name.casefold() for name in session.scalars(select(Category.name))}
    added = 0
    changed = False

    for category in session.scalars(select(Category).where(Category.is_active.is_(True))):
        if normalize_catalog_category_name(category.name) is None:
            category.is_active = False
            changed = True
            continue
        changed = apply_category_profile(category) or changed

    for entry in catalog.get("categories", []):
        raw_name = str(entry.get("name", ""))
        name = normalize_catalog_category_name(raw_name)
        if not name or name.casefold() in existing:
            continue
        category = Category(name=name, is_active=True)
        apply_category_profile(category)
        session.add(category)
        existing.add(name.casefold())
        added += 1

    if added or changed:
        session.flush()

    active_categories = {
        category.name: category for category in session.scalars(select(Category).where(Category.is_active.is_(True)))
    }
    existing_subcategories = {
        (subcategory.category_id, subcategory.name.casefold()): subcategory
        for subcategory in session.scalars(select(Subcategory))
    }
    for entry in catalog.get("categories", []):
        raw_name = str(entry.get("name", ""))
        name = normalize_catalog_category_name(raw_name)
        if not name:
            continue
        category = active_categories.get(name)
        if category is None:
            continue
        for raw_subcategory in entry.get("subcategories", []):
            subcategory_name = str(raw_subcategory).strip()
            if not subcategory_name:
                continue
            key = (category.id, subcategory_name.casefold())
            existing_subcategory = existing_subcategories.get(key)
            if existing_subcategory is None:
                session.add(Subcategory(category_id=category.id, name=subcategory_name, is_active=True))
                existing_subcategories[key] = True
                changed = True
            elif not existing_subcategory.is_active:
                existing_subcategory.is_active = True
                changed = True

    if added or changed:
        session.commit()
    _SYNC_STATE[cache_key] = state
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
