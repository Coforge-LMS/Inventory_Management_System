"""Shared pytest setup for the inventory tests."""

from contextlib import closing

import pytest

import inventory_db
import seed_db


@pytest.fixture
def db():
    """Give each test its own empty in-memory database with the schema loaded."""
    with closing(inventory_db.connect(":memory:")) as connection:
        inventory_db.init_schema(connection)
        yield connection


@pytest.fixture
def seeded_db(db):
    """The same database, filled with the sample data from seed_db.py."""
    seed_db.load_sample_data(db)
    return db