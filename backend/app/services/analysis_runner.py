import uuid
from collections import Counter
from datetime import UTC, datetime

from fastapi import HTTPException
from geoalchemy2.shape import from_shape, to_shape
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AnalysisResult, AnalysisRun, Feature, Layer
from app.services.analysis_engine import (
    GeoItem,
    analyze_building_parcel,
    analyze_egib_lpis,
    analyze_line_boundary,
)
from app.services.events import add_event

INPUT_ORDERS = {
    "BUILDING_PARCEL_RELATION": ["layer_buildings", "layer_parcels"],
    "EGIB_LPIS_OVERLAP": ["layer_egib", "layer_lpis"],
    "LINE_BOUNDARY_PROXIMITY": ["layer_lines", "layer_boundaries"],
}

DEFAULTS = {
    "BUILDING_PARCEL_RELATION": {"tolerance_m": 0.1, "min_outside_area_m2": 1.0, "classify_touch_as_candidate": True},
    "EGIB_LPIS_OVERLAP": {"min_intersection_area_m2": 1.0, "min_overlap_percent": 80.0, "sliver_area_threshold_m2": 5.0, "tolerance_m": 0.1},
    "LINE_BOUNDARY_PROXIMITY": {"tolerance_m": 0.3, "min_matching_length_m": 2.0, "min_matching_percent": 50.0},
}


def _features(db: Session, layer_id: uuid.UUID) -> list[GeoItem]:
    rows = db.scalars(select(Feature).where(Feature.layer_id == layer_id)).all()
    return [GeoItem(row.id, to_shape(row.geom)) for row in rows]


def _validate_layers(db: Session, project_id: uuid.UUID, ordered_ids: list[uuid.UUID], analysis_key: str) -> None:
    layers = [db.get(Layer, layer_id) for layer_id in ordered_ids]
    if any(layer is None or layer.project_id != project_id for layer in layers):
        raise HTTPException(status_code=422, detail="Warstwy wejściowe muszą należeć do projektu")
    types = [layer.geometry_type for layer in layers if layer]
    if analysis_key in {"BUILDING_PARCEL_RELATION", "EGIB_LPIS_OVERLAP"} and any("Polygon" not in item for item in types):
        raise HTTPException(status_code=422, detail="Ta analiza wymaga warstw poligonowych")
    if analysis_key == "LINE_BOUNDARY_PROXIMITY" and "Line" not in types[0]:
        raise HTTPException(status_code=422, detail="Pierwsza warstwa analizy musi być liniowa")


def create_and_run_analysis(
    db: Session,
    *,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    analysis_key: str,
    name: str | None,
    inputs: dict[str, uuid.UUID],
    parameters: dict,
) -> AnalysisRun:
    if analysis_key not in INPUT_ORDERS:
        raise HTTPException(status_code=422, detail="Nieobsługiwana analiza")
    expected = INPUT_ORDERS[analysis_key]
    if set(inputs) != set(expected):
        raise HTTPException(status_code=422, detail=f"Wymagane wejścia: {', '.join(expected)}")
    ordered_ids = [inputs[key] for key in expected]
    _validate_layers(db, project_id, ordered_ids, analysis_key)
    merged = {**DEFAULTS[analysis_key], **parameters}
    for key, value in merged.items():
        if key != "classify_touch_as_candidate" and (not isinstance(value, (int, float)) or value < 0):
            raise HTTPException(status_code=422, detail=f"Parametr {key} musi być liczbą nieujemną")
    run = AnalysisRun(project_id=project_id, analysis_key=analysis_key, name=name or analysis_key, status="PENDING", input_layer_ids=ordered_ids, parameters_json=merged, result_summary_json={}, created_by_user_id=user_id)
    db.add(run)
    db.commit()
    try:
        run.status = "RUNNING"
        run.started_at = datetime.now(UTC)
        db.commit()
        first, second = _features(db, ordered_ids[0]), _features(db, ordered_ids[1])
        if analysis_key == "BUILDING_PARCEL_RELATION":
            outcomes = analyze_building_parcel(first, second, **merged)
        elif analysis_key == "EGIB_LPIS_OVERLAP":
            outcomes = analyze_egib_lpis(first, second, **merged)
        else:
            outcomes = analyze_line_boundary(first, second, **merged)
        for outcome in outcomes:
            db.add(AnalysisResult(analysis_run_id=run.id, project_id=project_id, result_type=outcome.result_type, severity=outcome.severity, label=outcome.label, description=outcome.description, recommendation=outcome.recommendation, metrics_json=outcome.metrics, feature_a_id=outcome.feature_a_id, feature_b_id=outcome.feature_b_id, geom=from_shape(outcome.geom, srid=2180) if outcome.geom and not outcome.geom.is_empty else None))
        run.result_summary_json = {"result_count": len(outcomes), "by_type": dict(Counter(o.result_type for o in outcomes)), "by_severity": dict(Counter(o.severity for o in outcomes))}
        run.status = "DONE"
        run.finished_at = datetime.now(UTC)
        run.log_text = f"Analiza zakończona. Wyników: {len(outcomes)}."
        add_event(db, project_id=project_id, entity_type="analysis_run", entity_id=run.id, user_id=user_id, message=f"Zakończono analizę „{run.name}”.", details=run.result_summary_json)
        db.commit()
        db.refresh(run)
        return run
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        db.execute(delete(AnalysisResult).where(AnalysisResult.analysis_run_id == run.id))
        run = db.get(AnalysisRun, run.id)
        run.status = "ERROR"
        run.error_message = str(exc)
        run.log_text = f"Analiza przerwana: {exc}"
        run.finished_at = datetime.now(UTC)
        add_event(db, project_id=project_id, entity_type="analysis_run", entity_id=run.id, user_id=user_id, level="ERROR", message="Analiza nie została zakończona.", details={"reason": str(exc)})
        db.commit()
        raise HTTPException(status_code=422, detail={"message": str(exc), "run_id": str(run.id)}) from exc

