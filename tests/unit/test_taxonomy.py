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
                    {"name": "Rule clarification request"},
                ],
            }
        ),
        encoding="utf-8",
    )

    added = sync_taxonomy_catalog(session, catalog_path)

    assert added == 2

    categories = list(session.scalars(select(Category).order_by(Category.name)))
    assert {category.name for category in categories} == {
        "Informational only",
        "Ineligible player",
        "Rule clarification request",
    }

    informational = next(category for category in categories if category.name == "Informational only")
    assert informational.is_active is False

    ineligible = next(category for category in categories if category.name == "Ineligible player")
    assert ineligible.is_active is True
