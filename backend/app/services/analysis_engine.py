import math
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


@dataclass(slots=True)
class GeoItem:
    id: uuid.UUID
    geom: BaseGeometry


@dataclass(slots=True)
class AnalysisOutcome:
    result_type: str
    severity: str
    label: str
    description: str
    recommendation: str
    metrics: dict[str, Any]
    feature_a_id: uuid.UUID | None
    feature_b_id: uuid.UUID | None
    geom: BaseGeometry | None


DISCLAIMER = "Wynik jest kandydatem do dalszej weryfikacji i nie rozstrzyga poprawności danych."


def _round_metrics(values: dict[str, Any]) -> dict[str, Any]:
    return {key: round(value, 4) if isinstance(value, float) and math.isfinite(value) else value for key, value in values.items()}


def analyze_building_parcel(
    buildings: list[GeoItem],
    parcels: list[GeoItem],
    *,
    tolerance_m: float = 0.1,
    min_outside_area_m2: float = 1.0,
    classify_touch_as_candidate: bool = True,
) -> list[AnalysisOutcome]:
    results: list[AnalysisOutcome] = []
    for building in buildings:
        nearby = [parcel for parcel in parcels if building.geom.distance(parcel.geom) <= tolerance_m]
        positive = [(parcel, building.geom.intersection(parcel.geom)) for parcel in nearby]
        positive = [(parcel, intersection) for parcel, intersection in positive if intersection.area > 0]
        parcel_count = len(positive)
        covered = unary_union([intersection for _, intersection in positive]) if positive else None
        intersection_area = covered.area if covered else 0.0
        outside_area = max(0.0, building.geom.area - intersection_area)
        best = max(positive, key=lambda pair: pair[1].area)[0] if positive else (nearby[0] if nearby else None)

        if not positive and nearby and classify_touch_as_candidate:
            result_type, severity = "BUILDING_TOUCHES_BOUNDARY", "LOW"
            label = "Budynek styka się z granicą działki"
        elif not positive:
            result_type, severity = "BUILDING_OUTSIDE_PARCEL", "HIGH"
            label = "Budynek poza zidentyfikowanymi działkami"
        elif parcel_count > 1:
            result_type, severity = "BUILDING_ON_MULTIPLE_PARCELS", "MEDIUM"
            label = "Budynek powiązany geometrycznie z wieloma działkami"
        elif outside_area > min_outside_area_m2:
            result_type, severity = "BUILDING_CROSSES_BOUNDARY", "MEDIUM"
            label = "Budynek przecina granicę działki"
        elif classify_touch_as_candidate and best and building.geom.distance(best.geom.boundary) <= tolerance_m:
            result_type, severity = "BUILDING_TOUCHES_BOUNDARY", "LOW"
            label = "Budynek styka się z granicą działki"
        else:
            result_type, severity = "BUILDING_WITHIN_PARCEL", "INFO"
            label = "Budynek położony wewnątrz działki"

        area = building.geom.area
        metrics = {
            "building_area_m2": area,
            "intersection_area_m2": intersection_area,
            "outside_area_m2": outside_area,
            "outside_area_percent": outside_area / area * 100 if area else 0.0,
            "parcel_count": parcel_count,
            "relation_de9im": building.geom.relate(best.geom) if best else None,
        }
        results.append(
            AnalysisOutcome(
                result_type,
                severity,
                label,
                f"{label} — kandydat do weryfikacji relacji budynek–działka. {DISCLAIMER}",
                "Porównaj geometrię i metadane obu warstw źródłowych.",
                _round_metrics(metrics),
                building.id,
                best.id if best else None,
                building.geom,
            )
        )
    return results


def analyze_egib_lpis(
    egib_items: list[GeoItem],
    lpis_items: list[GeoItem],
    *,
    min_intersection_area_m2: float = 1.0,
    min_overlap_percent: float = 80.0,
    sliver_area_threshold_m2: float = 5.0,
    tolerance_m: float = 0.1,
) -> list[AnalysisOutcome]:
    results: list[AnalysisOutcome] = []
    matched_egib: set[uuid.UUID] = set()
    matched_lpis: set[uuid.UUID] = set()
    for egib in egib_items:
        for lpis in lpis_items:
            distance = egib.geom.distance(lpis.geom)
            if distance > tolerance_m and not egib.geom.intersects(lpis.geom):
                continue
            intersection = egib.geom.intersection(lpis.geom)
            intersection_area = intersection.area
            if intersection_area < min_intersection_area_m2:
                results.append(
                    AnalysisOutcome(
                        "SLIVER_OR_GAP_CANDIDATE",
                        "LOW",
                        "Możliwa szczelina lub fragment resztkowy",
                        f"Geometrie znajdują się blisko siebie, lecz ich pokrycie jest niewielkie. {DISCLAIMER}",
                        "Zweryfikuj tolerancję i jakość geometrii źródłowych.",
                        _round_metrics({"intersection_area_m2": intersection_area, "distance_m": distance}),
                        egib.id,
                        lpis.id,
                        intersection if not intersection.is_empty else egib.geom.boundary,
                    )
                )
                continue

            matched_egib.add(egib.id)
            matched_lpis.add(lpis.id)
            area_e, area_l = egib.geom.area, lpis.geom.area
            pct_e = intersection_area / area_e * 100 if area_e else 0.0
            pct_l = intersection_area / area_l * 100 if area_l else 0.0
            union_area = egib.geom.union(lpis.geom).area
            if pct_e >= min_overlap_percent and pct_l >= min_overlap_percent:
                result_type, severity, label = "STRONG_OVERLAP", "INFO", "Silne pokrycie EGiB–LPIS"
            elif pct_e >= min_overlap_percent or pct_l >= min_overlap_percent:
                result_type, severity, label = "PARTIAL_OVERLAP", "MEDIUM", "Częściowe pokrycie EGiB–LPIS"
            else:
                result_type, severity, label = "LOW_OVERLAP", "MEDIUM", "Niskie pokrycie EGiB–LPIS"
            metrics = {
                "area_egib_m2": area_e,
                "area_lpis_m2": area_l,
                "intersection_area_m2": intersection_area,
                "overlap_egib_percent": pct_e,
                "overlap_lpis_percent": pct_l,
                "union_area_m2": union_area,
                "jaccard_index": intersection_area / union_area if union_area else 0.0,
            }
            results.append(
                AnalysisOutcome(
                    result_type,
                    severity,
                    label,
                    f"Obiekt LPIS pokrywa się geometrycznie z obiektem EGiB. LPIS jest źródłem pomocniczym. {DISCLAIMER}",
                    "Porównaj zakres, aktualność i przeznaczenie obu rejestrów.",
                    _round_metrics(metrics),
                    egib.id,
                    lpis.id,
                    intersection,
                )
            )
            remainders = [area_e - intersection_area, area_l - intersection_area]
            if any(0 < value <= sliver_area_threshold_m2 for value in remainders):
                results.append(
                    AnalysisOutcome(
                        "SLIVER_OR_GAP_CANDIDATE",
                        "LOW",
                        "Mały fragment różnicowy",
                        f"W relacji powierzchniowej występuje mały fragment resztkowy. {DISCLAIMER}",
                        "Sprawdź wpływ tolerancji i dokładności źródeł.",
                        _round_metrics({"egib_remainder_m2": remainders[0], "lpis_remainder_m2": remainders[1]}),
                        egib.id,
                        lpis.id,
                        egib.geom.symmetric_difference(lpis.geom),
                    )
                )

    for item in egib_items:
        if item.id not in matched_egib:
            results.append(AnalysisOutcome("EGIB_WITHOUT_LPIS_MATCH", "HIGH", "Obiekt EGiB bez dopasowania LPIS", f"Nie znaleziono kwalifikującego pokrycia z LPIS. {DISCLAIMER}", "Sprawdź zakres i aktualność warstwy LPIS.", {"area_egib_m2": round(item.geom.area, 4)}, item.id, None, item.geom))
    for item in lpis_items:
        if item.id not in matched_lpis:
            results.append(AnalysisOutcome("LPIS_WITHOUT_EGIB_MATCH", "HIGH", "Obiekt LPIS bez dopasowania EGiB", f"Nie znaleziono kwalifikującego pokrycia z EGiB. {DISCLAIMER}", "Sprawdź zakres i aktualność warstwy EGiB.", {"area_lpis_m2": round(item.geom.area, 4)}, item.id, None, item.geom))
    return results


def _distance_samples(line: BaseGeometry, boundary: BaseGeometry, tolerance: float) -> list[float]:
    if line.length == 0:
        return [line.distance(boundary)]
    spacing = max(tolerance / 2, 0.1)
    count = min(10_000, max(2, math.ceil(line.length / spacing) + 1))
    return [line.interpolate(i / (count - 1), normalized=True).distance(boundary) for i in range(count)]


def analyze_line_boundary(
    lines: list[GeoItem],
    boundaries: list[GeoItem],
    *,
    tolerance_m: float = 0.3,
    min_matching_length_m: float = 2.0,
    min_matching_percent: float = 50.0,
) -> list[AnalysisOutcome]:
    boundary_geoms = [item.geom.boundary if "Polygon" in item.geom.geom_type else item.geom for item in boundaries]
    boundary = unary_union(boundary_geoms)
    results: list[AnalysisOutcome] = []
    for line in lines:
        matching = line.geom.intersection(boundary.buffer(tolerance_m)) if not boundary.is_empty else line.geom.intersection(boundary)
        matching_length = matching.length
        percent = matching_length / line.geom.length * 100 if line.geom.length else 0.0
        distances = _distance_samples(line.geom, boundary, tolerance_m) if not boundary.is_empty else []
        if not boundary.is_empty and line.geom.crosses(boundary):
            result_type, severity, label = "LINE_CROSSES_BOUNDARY", "MEDIUM", "Linia przecina granicę"
        elif matching_length >= min_matching_length_m and percent >= min_matching_percent:
            result_type, severity, label = "POSSIBLE_LINE_BOUNDARY_MATCH", "INFO", "Możliwe dopasowanie linii do granicy"
        elif matching_length > 0:
            result_type, severity, label = "PARTIAL_LINE_BOUNDARY_MATCH", "LOW", "Częściowe dopasowanie linii do granicy"
        else:
            result_type, severity, label = "NO_SIGNIFICANT_MATCH", "INFO", "Brak istotnego dopasowania linii"
        metrics = {
            "line_length_m": line.geom.length,
            "matching_length_m": matching_length,
            "matching_percent": percent,
            "min_distance_m": min(distances) if distances else None,
            "max_distance_m": max(distances) if distances else None,
            "avg_distance_m": sum(distances) / len(distances) if distances else None,
        }
        results.append(
            AnalysisOutcome(
                result_type,
                severity,
                label,
                f"Relację linii i granicy oceniono dla zadanej tolerancji. {DISCLAIMER}",
                "Porównaj wynik z materiałami źródłowymi i przyjętą tolerancją.",
                _round_metrics(metrics),
                line.id,
                None,
                matching if not matching.is_empty else line.geom,
            )
        )
    return results


def summarize(outcomes: list[AnalysisOutcome]) -> dict[str, Any]:
    return {"result_count": len(outcomes), "by_type": dict(Counter(item.result_type for item in outcomes)), "by_severity": dict(Counter(item.severity for item in outcomes))}
