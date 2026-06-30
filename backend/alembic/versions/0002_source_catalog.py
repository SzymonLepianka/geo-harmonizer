"""Verified source catalog and guided import metadata.

Revision ID: 0002_source_catalog
Revises: 0001_initial
"""

import json
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_source_catalog"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


VERIFIED_AT = datetime(2026, 6, 30, tzinfo=UTC)


def _entry(
    key: str,
    name: str,
    category: str,
    provider: str,
    service_type: str,
    import_mode: str,
    description: str,
    *,
    service_url: str | None = None,
    documentation_url: str | None = None,
    dataset_version: str | None = None,
    layer_type: str | None = None,
    geometry_type: str | None = None,
    scope: str | None = None,
    limitations: str | None = None,
    instructions: str | None = None,
    legal_note: str | None = None,
    config: dict | None = None,
    active: bool = True,
    status: str = "IMPLEMENTED",
    sort_order: int = 100,
) -> dict:
    return {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, f"geoharmonizer:{key}"),
        "key": key,
        "name": name,
        "category": category,
        "implementation_status": status,
        "access_mode": import_mode,
        "description": description,
        "limitations": limitations,
        "instruction_md": instructions,
        "provider": provider,
        "service_type": service_type,
        "service_url": service_url,
        "documentation_url": documentation_url,
        "import_mode": import_mode,
        "dataset_version": dataset_version,
        "default_layer_type": layer_type,
        "geometry_type": geometry_type,
        "geographic_scope": scope,
        "legal_note": legal_note,
        "adapter_config": config or {},
        "is_active": active,
        "sort_order": sort_order,
        "last_verified_at": VERIFIED_AT,
        "last_check_status": "AVAILABLE" if active and import_mode == "AUTOMATIC" else None,
        "last_check_message": "Zweryfikowano 30.06.2026." if active else "Usługa nie przeszła kontroli dostępności 30.06.2026.",
        "last_checked_at": VERIFIED_AT,
    }


WFS_GUGIK = {
    "version": "2.0.0",
    "response_format": "GML",
    "bbox_crs": "EPSG:4326",
    "axis_order": "yx",
    "type_name_parameter": "typeNames",
    "limit_parameter": "count",
    "feature_limit": 1000,
    "hits_attribute": "numberMatched",
}
WFS_ZYWIEC = {
    "version": "1.1.0",
    "response_format": "GML",
    "bbox_crs": "EPSG:4326",
    "axis_order": "yx",
    "type_name_parameter": "typeName",
    "limit_parameter": "maxFeatures",
    "hits_attribute": "numberOfFeatures",
}
WFS_ARIMR = {
    "version": "2.0.0",
    "response_format": "GeoJSON",
    "output_format": "application/json",
    "bbox_crs": "EPSG:4326",
    "axis_order": "xy",
    "type_name_parameter": "typeNames",
    "limit_parameter": "count",
    "hits_attribute": "numberMatched",
}


ENTRIES = [
    _entry(
        "GUGIK_EGIB_PARCELS_WFS", "EGiB — działki (usługa krajowa)", "EGiB", "GUGiK", "WFS", "AUTOMATIC",
        "Zbiorcza usługa pobierania działek ewidencyjnych z usług powiatowych.",
        service_url="https://mapy.geoportal.gov.pl/wss/service/PZGIK/EGIB/WFS/UslugaZbiorcza",
        documentation_url="https://www.geoportal.gov.pl/pl/dane/ewidencja-gruntow-i-budynkow-egib/",
        layer_type="EGIB_PARCELS", geometry_type="Polygon", scope="Polska", sort_order=10,
        legal_note="Dane publiczne EGiB; nie zawierają danych właścicieli i nie zastępują dokumentów urzędowych.",
        limitations="Zbiorczy endpoint ma limit 1000 obiektów, a jego stronicowanie jest niespójne. Dla większej próbki użyj bezpośredniej usługi powiatowej.",
        config={**WFS_GUGIK, "typename": "ms:dzialki"},
    ),
    _entry(
        "GUGIK_EGIB_BUILDINGS_WFS", "EGiB — budynki (usługa krajowa)", "EGiB", "GUGiK", "WFS", "AUTOMATIC",
        "Zbiorcza usługa pobierania geometrii i podstawowych atrybutów budynków EGiB.",
        service_url="https://mapy.geoportal.gov.pl/wss/service/PZGIK/EGIB/WFS/UslugaZbiorcza",
        documentation_url="https://www.geoportal.gov.pl/pl/dane/ewidencja-gruntow-i-budynkow-egib/",
        layer_type="EGIB_BUILDINGS", geometry_type="Polygon", scope="Polska", sort_order=20,
        limitations="Zakres atrybutów zależy od źródłowej usługi powiatowej. Zbiorczy endpoint ma bezpieczny limit 1000 obiektów; większy zakres pobierz z WFS powiatowego.",
        config={**WFS_GUGIK, "typename": "ms:budynki"},
    ),
    _entry(
        "ZYWIEC_EGIB_PARCELS_WFS", "Powiat żywiecki — działki EGiB", "EGiB", "Powiat Żywiecki", "WFS", "AUTOMATIC",
        "Bezpośrednia powiatowa usługa WFS, przydatna jako studium przypadku i punkt odniesienia dla usługi krajowej.",
        service_url="https://zywiecki-wms.webewid.pl/iip/ows",
        documentation_url="https://wms16.epodgik.pl/walidator/data/files/reports/2025_04_10/raport_wfs_2417_2025_04_10.pdf",
        layer_type="EGIB_PARCELS", geometry_type="Polygon", scope="Powiat żywiecki (TERYT 2417)", sort_order=30,
        config={**WFS_ZYWIEC, "typename": "ms:dzialki"},
    ),
    _entry(
        "ZYWIEC_EGIB_BUILDINGS_WFS", "Powiat żywiecki — budynki EGiB", "EGiB", "Powiat Żywiecki", "WFS", "AUTOMATIC",
        "Bezpośrednia powiatowa usługa WFS budynków EGiB.",
        service_url="https://zywiecki-wms.webewid.pl/iip/ows",
        documentation_url="https://wms16.epodgik.pl/walidator/data/files/reports/2025_04_10/raport_wfs_2417_2025_04_10.pdf",
        layer_type="EGIB_BUILDINGS", geometry_type="Polygon", scope="Powiat żywiecki (TERYT 2417)", sort_order=40,
        config={**WFS_ZYWIEC, "typename": "ms:budynki"},
    ),
    _entry(
        "ARIMR_LPIS_REFERENCE_WFS", "LPIS — działki referencyjne", "LPIS", "ARiMR", "WFS", "AUTOMATIC",
        "Granice i identyfikatory działek referencyjnych LPIS.",
        service_url="https://geoportal-w1.arimr.gov.pl/geoserver/lpis_public/dzialki_referencyjne/wfs",
        documentation_url="https://www.gov.pl/web/arimr/arimr-otwiera-dane-przestrzenne-ze-swoich-zasobow",
        layer_type="LPIS_REFERENCE_PARCELS", geometry_type="Polygon", scope="Polska", sort_order=50,
        legal_note="LPIS jest źródłem pomocniczym, a nie wzorcem prawnego przebiegu granic.",
        config={**WFS_ARIMR, "typename": "lpis_public:dzialki_referencyjne"},
    ),
    _entry(
        "ARIMR_LPIS_MKO_WFS", "LPIS — maksymalny obszar kwalifikowany (MKO)", "LPIS", "ARiMR", "WFS", "AUTOMATIC",
        "Maksymalny kwalifikujący się obszar wraz z powierzchnią.",
        service_url="https://geoportal-w1.arimr.gov.pl/geoserver/lpis_public/mko_jpo/wfs",
        documentation_url="https://www.gov.pl/web/arimr/arimr-otwiera-dane-przestrzenne-ze-swoich-zasobow",
        layer_type="LPIS_MKO", geometry_type="Polygon", scope="Polska", sort_order=60,
        config={**WFS_ARIMR, "typename": "lpis_public:mko_jpo"},
    ),
    _entry(
        "ARIMR_LPIS_PZ_WFS", "LPIS — pokrycie terenu (powierzchnie)", "LPIS", "ARiMR", "WFS", "AUTOMATIC",
        "Powierzchniowe obiekty pokrycia terenu LPIS, m.in. lasy, wody, sady i uprawy trwałe.",
        service_url="https://geoportal-w1.arimr.gov.pl/geoserver/lpis_public/pokrycie_terenu_wfs/wfs",
        documentation_url="https://www.gov.pl/web/arimr/arimr-otwiera-dane-przestrzenne-ze-swoich-zasobow",
        layer_type="LPIS_PZ", geometry_type="Polygon", scope="Polska", sort_order=70,
        limitations="Preset obejmuje powierzchnie; obiekty liniowe i punktowe są publikowane jako osobne paczki.",
        config={**WFS_ARIMR, "typename": "lpis_public:pokrycie_terenu_wfs"},
    ),
    _entry(
        "ARIMR_GSA_2025_CROPS_WFS", "GSA 2025 — uprawy rolne", "GSA", "ARiMR", "WFS", "AUTOMATIC",
        "Zanonimizowane geometrie deklarowanych upraw rolnych z kampanii 2025.",
        service_url="https://geoportal-w2.arimr.gov.pl/geoserver/gsa_public/uprawy_2025/wfs",
        documentation_url="https://www.gov.pl/web/arimr/arimr-otwiera-dane-przestrzenne-ze-swoich-zasobow",
        dataset_version="2025", layer_type="LPIS_GSA", geometry_type="Polygon", scope="Polska", sort_order=80,
        config={**WFS_ARIMR, "typename": "gsa_public:uprawy_rolne_2025"},
    ),
    _entry(
        "ARIMR_GSA_2025_ARABLE_WFS", "GSA 2025 — uprawy na gruntach ornych", "GSA", "ARiMR", "WFS", "AUTOMATIC",
        "Geometrie upraw zadeklarowanych na gruntach ornych w kampanii 2025.",
        service_url="https://geoportal-w2.arimr.gov.pl/geoserver/gsa_public/uprawy_2025/wfs",
        documentation_url="https://www.gov.pl/web/arimr/arimr-otwiera-dane-przestrzenne-ze-swoich-zasobow",
        dataset_version="2025", layer_type="LPIS_GSA", geometry_type="Polygon", scope="Polska", sort_order=90,
        config={**WFS_ARIMR, "typename": "gsa_public:uprawy_na_gruntach_ornych_2025"},
    ),
    _entry(
        "ARIMR_GSA_2025_TUZ_WFS", "GSA 2025 — trwałe użytki zielone", "GSA", "ARiMR", "WFS", "AUTOMATIC",
        "Geometrie trwałych użytków zielonych zadeklarowanych w kampanii 2025.",
        service_url="https://geoportal-w2.arimr.gov.pl/geoserver/gsa_public/uprawy_tuz_2025/wfs",
        documentation_url="https://www.gov.pl/web/arimr/arimr-otwiera-dane-przestrzenne-ze-swoich-zasobow",
        dataset_version="2025", layer_type="LPIS_GSA", geometry_type="Polygon", scope="Polska", sort_order=100,
        config={**WFS_ARIMR, "typename": "gsa_public:uprawy_tuz_2025"},
    ),
    _entry(
        "ARIMR_GSA_2026_SLASKIE_SHP", "GSA 2026 — uprawy, woj. śląskie", "GSA", "ARiMR", "DOWNLOAD", "MANUAL_DOWNLOAD",
        "Wojewódzka paczka SHP z danymi kampanii 2026.", dataset_version="2026", layer_type="LPIS_GSA",
        geometry_type="Polygon", scope="Województwo śląskie", sort_order=200,
        documentation_url="https://geoportal.arimr.gov.pl/mapy/apps/sites/#/portal",
        limitations="Paczka ma około 95 MB. Pobierz ją w przeglądarce, a następnie wgraj jako SHP ZIP.",
        instructions="1. Pobierz [paczkę SHP ARiMR](https://geoportal.arimr.gov.pl/mapy/sharing/rest/content/items/71218e48e2154f698d065547bf59d1e4/data).\n2. Nie rozpakowuj ZIP.\n3. Wgraj plik w sekcji „Mam już plik” i wybierz profil LPIS/GSA.",
        config={"download_url": "https://geoportal.arimr.gov.pl/mapy/sharing/rest/content/items/71218e48e2154f698d065547bf59d1e4/data", "expected_size_mb": 95},
    ),
    _entry(
        "GUGIK_BDOT10K_ZYWIEC_GML", "BDOT10k — powiat żywiecki", "BDOT10k", "GUGiK", "DOWNLOAD", "MANUAL_DOWNLOAD",
        "Oficjalna powiatowa paczka BDOT10k w schemacie GML 2021.", dataset_version="stan publikacji 07.12.2023",
        layer_type="BDOT10K", scope="Powiat żywiecki (TERYT 2417)", sort_order=210,
        documentation_url="https://www.geoportal.gov.pl/pl/dane/baza-danych-obiektow-topograficznych-bdot10k/",
        limitations="Paczka ma około 125 MB i zawiera wiele klas obiektów. Obecny importer czyta pojedynczą warstwę.",
        instructions="1. Pobierz [paczkę GML](https://opendata.geoportal.gov.pl/bdot10k/schemat2021/24/2417_GML.zip).\n2. Rozpakuj ją lokalnie.\n3. W QGIS wybierz potrzebną klasę i wyeksportuj ją do GeoPackage lub GeoJSON.\n4. Wgraj wyeksportowany plik w sekcji „Mam już plik”.",
        config={"download_url": "https://opendata.geoportal.gov.pl/bdot10k/schemat2021/24/2417_GML.zip", "expected_size_mb": 125},
    ),
    _entry(
        "ZYWIEC_BDOT500_PZGIK", "BDOT500 — powiat żywiecki", "BDOT500", "Powiat Żywiecki", "PZGIK", "MANUAL_ORDER",
        "Szczegółowa baza obiektów topograficznych prowadzona przez powiat.", layer_type="BDOT500_FENCES",
        scope="Powiat żywiecki", sort_order=300,
        documentation_url="https://mapy.zywiec.powiat.pl/",
        limitations="Nie potwierdzono publicznej usługi pobierania. Materiał może podlegać opłacie i ograniczeniom zakresu.",
        instructions="1. Otwórz [Portal Interesanta](https://mapy.zywiec.powiat.pl/).\n2. Zaloguj się profilem zaufanym.\n3. Zamów cyfrowe dane BDOT500 dla badanego obszaru, preferując GML.\n4. Opłać zamówienie, jeśli urząd naliczy opłatę.\n5. Po pobraniu wyeksportuj potrzebną klasę do GeoPackage/GeoJSON i wgraj ją do GeoHarmonizera.",
    ),
    _entry(
        "ZYWIEC_GESUT_PZGIK", "GESUT — powiat żywiecki", "GESUT", "Powiat Żywiecki", "PZGIK", "MANUAL_ORDER",
        "Powiatowa baza geodezyjnej ewidencji sieci uzbrojenia terenu.", layer_type="GESUT_NETWORKS",
        scope="Powiat żywiecki", sort_order=310,
        documentation_url="https://mapy.zywiec.powiat.pl/",
        limitations="Nie potwierdzono publicznej usługi pobierania. Materiał może podlegać opłacie i ograniczeniom zakresu.",
        instructions="1. Otwórz [Portal Interesanta](https://mapy.zywiec.powiat.pl/).\n2. Zaloguj się profilem zaufanym.\n3. Zamów cyfrowe dane GESUT dla badanego obszaru.\n4. Po realizacji przygotuj wybraną warstwę liniową w QGIS i wgraj ją do aplikacji.",
    ),
    _entry(
        "GUGIK_PRG_WFS", "Państwowy Rejestr Granic", "PRG", "GUGiK", "WFS", "AUTOMATIC",
        "Urzędowe granice jednostek podziału terytorialnego.",
        service_url="https://mapy.geoportal.gov.pl/wss/service/PZGIK/PRG/WFS/AdministrativeBoundaries",
        documentation_url="https://www.geoportal.gov.pl/pl/dane/panstwowy-rejestr-granic-prg/",
        layer_type="ADMIN_BOUNDARIES", geometry_type="Polygon", scope="Polska", sort_order=400,
        active=False, status="TEMPORARILY_UNAVAILABLE",
        limitations="Podczas kontroli 30.06.2026 GetCapabilities zwracał HTTP 502. Import pozostaje zablokowany.",
        config={"version": "2.0.0"},
    ),
    _entry(
        "GUGIK_KIEG_WMS", "KIEG — krajowy podgląd EGiB", "EGiB", "GUGiK", "WMS", "VIEW_ONLY",
        "Usługa przeglądania mapy ewidencyjnej; nie przekazuje geometrii wektorowej do analiz.",
        service_url="https://services.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow",
        documentation_url="https://integracja.gugik.gov.pl/", scope="Polska", status="VIEW_ONLY", sort_order=500,
        limitations="WMS jest obrazem mapy. Nie można go importować jako obiekty wektorowe.",
    ),
    _entry(
        "GUGIK_KIUT_WMS", "KIUT — krajowy podgląd uzbrojenia terenu", "GESUT", "GUGiK", "WMS", "VIEW_ONLY",
        "Integracyjna usługa przeglądania uzbrojenia terenu.",
        documentation_url="https://integracja.gugik.gov.pl/", scope="Polska", status="VIEW_ONLY", sort_order=510,
        limitations="WMS służy wyłącznie do podglądu i nie dostarcza geometrii do analiz.",
    ),
    _entry(
        "GUGIK_KIBDOT_WMS", "KIBDOT — krajowy podgląd BDOT500", "BDOT500", "GUGiK", "WMS", "VIEW_ONLY",
        "Integracyjna usługa przeglądania baz BDOT500.",
        documentation_url="https://integracja.gugik.gov.pl/", scope="Polska", status="VIEW_ONLY", sort_order=520,
        limitations="WMS służy wyłącznie do podglądu i nie dostarcza geometrii do analiz.",
    ),
]


def upgrade() -> None:
    columns = [
        sa.Column("provider", sa.Text()),
        sa.Column("service_type", sa.String()),
        sa.Column("service_url", sa.Text()),
        sa.Column("documentation_url", sa.Text()),
        sa.Column("import_mode", sa.String(), nullable=False, server_default="MANUAL_UPLOAD"),
        sa.Column("dataset_version", sa.String()),
        sa.Column("default_layer_type", sa.String()),
        sa.Column("geometry_type", sa.String()),
        sa.Column("geographic_scope", sa.Text()),
        sa.Column("legal_note", sa.Text()),
        sa.Column("adapter_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_check_status", sa.String()),
        sa.Column("last_check_message", sa.Text()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
    ]
    for column in columns:
        op.add_column("source_registry", column)

    bind = op.get_bind()
    # Existing rows stay available through the historical registry endpoint, but
    # only the dated, verified presets below are active in the guided catalog.
    bind.execute(sa.text("UPDATE source_registry SET is_active = false"))
    statement = sa.text(
        """
        INSERT INTO source_registry (
            id, key, name, category, implementation_status, access_mode, description,
            limitations, instruction_md, provider, service_type, service_url,
            documentation_url, import_mode, dataset_version, default_layer_type,
            geometry_type, geographic_scope, legal_note, adapter_config, is_active,
            sort_order, last_verified_at, last_check_status, last_check_message,
            last_checked_at, created_at
        ) VALUES (
            :id, :key, :name, :category, :implementation_status, :access_mode, :description,
            :limitations, :instruction_md, :provider, :service_type, :service_url,
            :documentation_url, :import_mode, :dataset_version, :default_layer_type,
            :geometry_type, :geographic_scope, :legal_note, CAST(:adapter_config AS jsonb),
            :is_active, :sort_order, :last_verified_at, :last_check_status,
            :last_check_message, :last_checked_at, now()
        )
        ON CONFLICT (key) DO UPDATE SET
            name = EXCLUDED.name, category = EXCLUDED.category,
            implementation_status = EXCLUDED.implementation_status,
            access_mode = EXCLUDED.access_mode, description = EXCLUDED.description,
            limitations = EXCLUDED.limitations, instruction_md = EXCLUDED.instruction_md,
            provider = EXCLUDED.provider, service_type = EXCLUDED.service_type,
            service_url = EXCLUDED.service_url, documentation_url = EXCLUDED.documentation_url,
            import_mode = EXCLUDED.import_mode, dataset_version = EXCLUDED.dataset_version,
            default_layer_type = EXCLUDED.default_layer_type,
            geometry_type = EXCLUDED.geometry_type, geographic_scope = EXCLUDED.geographic_scope,
            legal_note = EXCLUDED.legal_note, adapter_config = EXCLUDED.adapter_config,
            is_active = EXCLUDED.is_active, sort_order = EXCLUDED.sort_order,
            last_verified_at = EXCLUDED.last_verified_at,
            last_check_status = EXCLUDED.last_check_status,
            last_check_message = EXCLUDED.last_check_message,
            last_checked_at = EXCLUDED.last_checked_at
        """
    )
    for row in ENTRIES:
        bind.execute(statement, {**row, "adapter_config": json.dumps(row["adapter_config"])})


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM source_registry WHERE key = ANY(:keys)"),
        {"keys": [row["key"] for row in ENTRIES]},
    )
    for name in [
        "last_checked_at", "last_check_message", "last_check_status", "last_verified_at",
        "sort_order", "is_active", "adapter_config", "legal_note", "geographic_scope",
        "geometry_type", "default_layer_type", "dataset_version", "import_mode",
        "documentation_url", "service_url", "service_type", "provider",
    ]:
        op.drop_column("source_registry", name)
