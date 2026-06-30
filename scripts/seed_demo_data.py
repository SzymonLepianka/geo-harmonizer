"""Create an idempotent demo project with geometries in EPSG:2180."""

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from geoalchemy2.shape import from_shape  # noqa: E402
from shapely.geometry import LineString, box  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import DatasetImport, DataSource, Feature, Layer, Project, User  # noqa: E402
from app.services.events import add_event  # noqa: E402

NAMESPACE = uuid.UUID("f4c60d20-bef4-4f16-94c8-97ca54d4e204")


def uid(name: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, name)


def ensure_admin(db) -> User:
    settings = get_settings()
    user = db.scalar(select(User).where(User.email == settings.admin_email.lower()))
    if not user:
        user = User(id=uid("admin"), email=settings.admin_email.lower(), password_hash=hash_password(settings.admin_password), role="ADMIN", is_active=True)
        db.add(user)
        db.flush()
    return user


def add_layer(db, project: Project, source: DataSource, key: str, name: str, layer_type: str, geometry_type: str, objects: list[tuple[str, object, dict]]) -> None:
    import_record = DatasetImport(id=uid(f"import:{key}"), project_id=project.id, data_source_id=source.id, status="DONE", original_filename=f"demo-{key}.geojson", detected_format="SAMPLE", detected_crs="EPSG:2180", target_crs="EPSG:2180", feature_count=len(objects), metadata_json={"demo": True}, log_text="Dane wygenerowane lokalnie przez seed demo.")
    layer = Layer(id=uid(f"layer:{key}"), project_id=project.id, dataset_import_id=import_record.id, name=name, layer_type=layer_type, geometry_type=geometry_type, srid=2180, attribute_schema={"name": "str", "case": "str"})
    db.add(import_record)
    db.flush()
    db.add(layer)
    db.flush()
    for object_key, geometry, attributes in objects:
        db.add(Feature(id=uid(f"feature:{object_key}"), project_id=project.id, layer_id=layer.id, external_id=object_key, source_object_id=object_key, attributes=attributes, geom=from_shape(geometry, srid=2180)))


def main() -> None:
    with SessionLocal() as db:
        admin = ensure_admin(db)
        project_id = uid("project")
        if db.get(Project, project_id):
            print("Projekt demo już istnieje; seed jest idempotentny.")
            db.commit()
            return
        project = Project(id=project_id, name="GeoHarmonizer — projekt demo", description="Lokalne geometrie demonstracyjne do testowania wszystkich analiz.", area_name="Obszar syntetyczny EPSG:2180", created_by_user_id=admin.id)
        source = DataSource(id=uid("source"), project_id=project.id, name="Dane syntetyczne GeoHarmonizer", source_type="SAMPLE", registry_key="SAMPLE", description="Dane wygenerowane lokalnie; nie reprezentują rzeczywistego obszaru.")
        db.add(project)
        db.flush()
        db.add(source)
        db.flush()
        parcels = [
            ("parcel-a", box(500000, 500000, 500100, 500100), {"name": "Działka A", "case": "demo"}),
            ("parcel-b", box(500100, 500000, 500200, 500100), {"name": "Działka B", "case": "demo"}),
        ]
        buildings = [
            ("building-within", box(500020, 500020, 500045, 500045), {"name": "Budynek wewnątrz", "case": "within"}),
            ("building-cross", box(500090, 500025, 500115, 500055), {"name": "Budynek przez granicę", "case": "cross"}),
        ]
        lpis = [
            ("lpis-strong", box(500002, 500002, 500098, 500098), {"name": "LPIS silne pokrycie", "case": "strong"}),
            ("lpis-partial", box(500150, 500050, 500230, 500130), {"name": "LPIS częściowe pokrycie", "case": "partial"}),
            ("lpis-unmatched", box(500260, 500000, 500310, 500050), {"name": "LPIS bez odpowiednika", "case": "unmatched"}),
        ]
        lines = [
            ("fence-near", LineString([(500000.2, 500005), (500000.2, 500095)]), {"name": "Linia blisko granicy", "case": "near"}),
            ("fence-cross", LineString([(500050, 499990), (500050, 500110)]), {"name": "Linia przecinająca granicę", "case": "cross"}),
        ]
        add_layer(db, project, source, "parcels", "Działki EGiB — demo", "EGIB_PARCELS", "Polygon", parcels)
        add_layer(db, project, source, "buildings", "Budynki EGiB — demo", "EGIB_BUILDINGS", "Polygon", buildings)
        add_layer(db, project, source, "lpis", "LPIS — demo", "LPIS_REFERENCE_PARCELS", "Polygon", lpis)
        add_layer(db, project, source, "fences", "Linie ogrodzeń — demo", "BDOT500_FENCES", "LineString", lines)
        add_event(db, project_id=project.id, entity_type="project", entity_id=project.id, user_id=admin.id, message="Utworzono kompletny projekt demonstracyjny.")
        db.commit()
        print("Utworzono projekt demo z działkami, budynkami, LPIS i liniami.")


if __name__ == "__main__":
    main()
