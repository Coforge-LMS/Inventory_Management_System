"""Test for backup_database."""

from contextlib import closing

import inventory_db


def test_a_backup_passes_the_integrity_check_and_has_the_same_row_counts(
    seeded_db, tmp_path
):
    backup_file = tmp_path / "backup.db"

    inventory_db.backup_database(seeded_db, backup_file)

    with closing(inventory_db.connect(backup_file)) as backup:
        assert inventory_db.integrity_check(backup) == "ok"
        original_counts = inventory_db.table_row_counts(seeded_db)
        assert inventory_db.table_row_counts(backup) == original_counts