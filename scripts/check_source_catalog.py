from app.database import SessionLocal
from app.models import SourceRegistry
from app.services.catalog_imports import check_catalog_source


def main() -> None:
    with SessionLocal() as db:
        sources = (
            db.query(SourceRegistry)
            .filter(
                SourceRegistry.service_type == "WFS",
                SourceRegistry.provider.is_not(None),
            )
            .order_by(SourceRegistry.sort_order, SourceRegistry.name)
            .all()
        )
        for source in sources:
            result = check_catalog_source(db, source)
            print(f"{result.status:11} {source.key:35} {result.message}")


if __name__ == "__main__":
    main()
