"""Shared pytest setup for the inventory tests."""

from contextlib import closing

import pytest


@pytest.fixture
def db():
    """Give each test its own empty in-memory database with the schema loaded."""
    # Imported here so this file can be committed before inventory_db.py exists.
    import inventory_db

    with closing(inventory_db.connect(":memory:")) as connection:
        inventory_db.init_schema(connection)
        yield connection