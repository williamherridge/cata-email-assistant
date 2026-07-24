import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from src.shared.database import Base
from src.shared.models import Category
from src.workflow.taxonomy import sync_taxonomy_catalog


def make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def test_sync_taxonomy_catalog_normalizes_and_excludes_labels(tmp_path: Path):
    session = make_session()
    session.add(Category(name="Informational only", is_active=True))
    session.commit()

    catalog_path = tmp_path / "taxonomy_catalog.json"
    catalog_path.write_text(
        json.dumps(
            {
                "updated_at": "2026-07-20T00:00:00",
                "categories": [
                    {"name": "Informational only"},
                    {"name": "Ineligible player"},
                    {"name": "Ineligible player for sectionals notification"},
                    {"name": "Make-up date form"},
                    {"name": "Make-up match line up"},
                    {"name": "Rule clarification request"},
                ],
            }
        ),
        encoding="utf-8",
    )

    added = sync_taxonomy_catalog(session, catalog_path)

    assert added == 4

    categories = list(session.scalars(select(Category).order_by(Category.name)))
    assert {category.name for category in categories} == {
        "Informational only",
        "Ineligible player",
        "Make-up date form",
        "Make-up match line up",
        "Rule clarification request",
    }

    informational = next(category for category in categories if category.name == "Informational only")
    assert informational.is_active is False

    ineligible = next(category for category in categories if category.name == "Ineligible player")
    assert ineligible.is_active is True

    makeup_date = next(category for category in categories if category.name == "Make-up date form")
    assert makeup_date.default_draft_behavior == "auto_ignore_candidate"
    assert makeup_date.default_reply_needed is False
    assert makeup_date.default_informational_only is True
    assert makeup_date.priority_hint == "low"

    makeup = next(category for category in categories if category.name == "Make-up match line up")
    assert makeup.default_draft_behavior == "auto_ignore_candidate"
    assert makeup.default_reply_needed is False
    assert makeup.default_informational_only is True
    assert makeup.priority_hint == "low"


def test_sync_taxonomy_catalog_ignores_invalid_json(tmp_path: Path):
    session = make_session()
    catalog_path = tmp_path / "taxonomy_catalog.json"
    catalog_path.write_text("{not valid json", encoding="utf-8")

    added = sync_taxonomy_catalog(session, catalog_path)

    assert added == 0
    assert list(session.scalars(select(Category))) == []
