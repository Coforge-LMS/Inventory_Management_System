"""Test for the low stock banner shown when the menu starts."""

import main


def test_the_banner_shows_the_number_of_low_stock_products(seeded_db, capsys):
    main.print_banner(seeded_db)

    # The sample data has three products at or below their reorder level.
    assert "Low stock products: 3" in capsys.readouterr().out