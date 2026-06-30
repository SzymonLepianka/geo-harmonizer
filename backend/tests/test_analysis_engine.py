import uuid

from shapely.geometry import LineString, box

from app.services.analysis_engine import (
    GeoItem,
    analyze_building_parcel,
    analyze_egib_lpis,
    analyze_line_boundary,
)


def item(geometry):
    return GeoItem(uuid.uuid4(), geometry)


def test_building_within_parcel():
    result = analyze_building_parcel([item(box(2, 2, 4, 4))], [item(box(0, 0, 10, 10))])[0]
    assert result.result_type == "BUILDING_WITHIN_PARCEL"
    assert result.metrics["outside_area_m2"] == 0


def test_building_crosses_boundary():
    result = analyze_building_parcel([item(box(8, 2, 12, 6))], [item(box(0, 0, 10, 10))], min_outside_area_m2=1)[0]
    assert result.result_type == "BUILDING_CROSSES_BOUNDARY"
    assert result.metrics["outside_area_m2"] == 8


def test_egib_lpis_strong_overlap():
    results = analyze_egib_lpis([item(box(0, 0, 10, 10))], [item(box(0.5, 0.5, 9.5, 9.5))])
    assert any(result.result_type == "STRONG_OVERLAP" for result in results)


def test_egib_lpis_partial_overlap():
    results = analyze_egib_lpis([item(box(0, 0, 10, 10))], [item(box(5, 0, 15, 10))])
    assert any(result.result_type == "LOW_OVERLAP" for result in results)


def test_line_within_tolerance():
    results = analyze_line_boundary([item(LineString([(0.2, 0), (0.2, 10)]))], [item(LineString([(0, 0), (0, 10)]))], tolerance_m=0.3, min_matching_length_m=2, min_matching_percent=50)
    assert results[0].result_type == "POSSIBLE_LINE_BOUNDARY_MATCH"
    assert results[0].metrics["matching_percent"] == 100


def test_result_copy_is_neutral():
    outcomes = []
    outcomes += analyze_building_parcel([item(box(8, 2, 12, 6))], [item(box(0, 0, 10, 10))])
    outcomes += analyze_egib_lpis([item(box(0, 0, 10, 10))], [item(box(5, 0, 15, 10))])
    outcomes += analyze_line_boundary([item(LineString([(0, 0), (10, 0)]))], [item(LineString([(5, -5), (5, 5)]))])
    forbidden = ["błąd danych", "naruszenie", "nielegalne", "zajęcie", "automatyczna poprawka"]
    for outcome in outcomes:
        text = f"{outcome.label} {outcome.description} {outcome.recommendation}".lower()
        assert not any(term in text for term in forbidden)

