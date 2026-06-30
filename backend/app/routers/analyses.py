import csv
import io
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_project_or_404, require_editor
from app.models import AnalysisDefinition, AnalysisResult, AnalysisRun, User
from app.schemas import AnalysisDefinitionOut, AnalysisResultOut, AnalysisRunCreate, AnalysisRunOut
from app.services.analysis_runner import create_and_run_analysis

router = APIRouter(tags=["analyses"])


@router.get("/api/analysis-definitions", response_model=list[AnalysisDefinitionOut])
def definitions(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[AnalysisDefinition]:
    return list(db.scalars(select(AnalysisDefinition).order_by(AnalysisDefinition.name)).all())


@router.post("/api/projects/{project_id}/analysis-runs", response_model=AnalysisRunOut, status_code=201)
def run_analysis(project_id: uuid.UUID, payload: AnalysisRunCreate, db: Session = Depends(get_db), user: User = Depends(require_editor)) -> AnalysisRun:
    get_project_or_404(project_id, db)
    return create_and_run_analysis(db, project_id=project_id, user_id=user.id, analysis_key=payload.analysis_key, name=payload.name, inputs=payload.inputs, parameters=payload.parameters)


@router.get("/api/projects/{project_id}/analysis-runs", response_model=list[AnalysisRunOut])
def list_runs(project_id: uuid.UUID, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[AnalysisRun]:
    get_project_or_404(project_id, db)
    return list(db.scalars(select(AnalysisRun).where(AnalysisRun.project_id == project_id).order_by(AnalysisRun.created_at.desc()).limit(limit).offset(offset)).all())


def _get_run(project_id: uuid.UUID, run_id: uuid.UUID, db: Session) -> AnalysisRun:
    run = db.get(AnalysisRun, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Nie znaleziono uruchomienia analizy")
    return run


@router.get("/api/projects/{project_id}/analysis-runs/{run_id}", response_model=AnalysisRunOut)
def get_run(project_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> AnalysisRun:
    return _get_run(project_id, run_id, db)


@router.get("/api/projects/{project_id}/analysis-runs/{run_id}/results", response_model=list[AnalysisResultOut])
def get_results(project_id: uuid.UUID, run_id: uuid.UUID, result_type: str | None = None, severity: str | None = None, limit: int = Query(1000, ge=1, le=5000), offset: int = Query(0, ge=0), db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[AnalysisResult]:
    _get_run(project_id, run_id, db)
    query = select(AnalysisResult).where(AnalysisResult.analysis_run_id == run_id)
    if result_type:
        query = query.where(AnalysisResult.result_type == result_type)
    if severity:
        query = query.where(AnalysisResult.severity == severity)
    return list(db.scalars(query.order_by(AnalysisResult.created_at).limit(limit).offset(offset)).all())


@router.get("/api/projects/{project_id}/analysis-runs/{run_id}/results.geojson")
def results_geojson(project_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Response:
    _get_run(project_id, run_id, db)
    rows = db.execute(select(AnalysisResult, func.ST_AsGeoJSON(func.ST_Transform(AnalysisResult.geom, 4326))).where(AnalysisResult.analysis_run_id == run_id, AnalysisResult.geom.is_not(None))).all()
    features = []
    for result, geometry in rows:
        features.append({"type": "Feature", "id": str(result.id), "geometry": json.loads(geometry), "properties": {"id": str(result.id), "result_type": result.result_type, "severity": result.severity, "label": result.label, "description": result.description, "recommendation": result.recommendation, "metrics": result.metrics_json}})
    return JSONResponse(
        content={"type": "FeatureCollection", "features": features},
        headers={"Content-Disposition": f'attachment; filename="analysis-{run_id}.geojson"'},
    )


@router.get("/api/projects/{project_id}/analysis-runs/{run_id}/results.csv")
def results_csv(project_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Response:
    _get_run(project_id, run_id, db)
    results = db.scalars(select(AnalysisResult).where(AnalysisResult.analysis_run_id == run_id).order_by(AnalysisResult.created_at)).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "result_type", "severity", "label", "description", "recommendation", "feature_a_id", "feature_b_id", "metrics_json"])
    for item in results:
        writer.writerow([item.id, item.result_type, item.severity, item.label, item.description, item.recommendation, item.feature_a_id or "", item.feature_b_id or "", json.dumps(item.metrics_json, ensure_ascii=False)])
    return Response(content="\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="analysis-{run_id}.csv"'})
