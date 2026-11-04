# Changelog

## [1.0.0] - 2026-11-04

### Added
- SQLite database with suppliers, products, sales, sale items and stock movements, enforced by STRICT tables, constraints, foreign keys and an index.
- Seed script with sample data.
- Product functions: add, look up with the supplier name, change price and delete (a product that has been sold cannot be deleted).
- Product search by name, SKU or supplier, with category, maximum price, in stock and low stock filters.
- Four reports: stock value by supplier, low stock, sales by product and never sold.
- Restock, stock adjustment and sale recording, each as one transaction, so a failed sale changes nothing.
- Terminal menu with friendly messages for bad input and database errors.
- Database backup using SQLite's backup function.
- Docker image that keeps the database on a volume, with the location set by `INVENTORY_DB`.
- GitHub Actions workflow with ruff, pytest and a Docker build that runs the tests inside the image.