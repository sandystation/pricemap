import numpy as np

from src.ml.features import FEATURE_NAMES, build_feature_vector


def test_build_feature_vector_basic():
    vec = build_feature_vector(
        lat=35.9,
        lon=14.5,
        property_type="apartment",
        area_sqm=80.0,
        floor=3,
        rooms=4,
        bedrooms=2,
        year_built=2005,
        condition="good",
    )
    assert isinstance(vec, np.ndarray)
    assert len(vec) == len(FEATURE_NAMES)
    assert vec[0] == 35.9  # lat
    assert vec[1] == 14.5  # lon
    assert vec[2] == 80.0  # area
    assert vec[3] == 3  # floor


def test_build_feature_vector_missing_fields():
    vec = build_feature_vector(
        lat=42.7,
        lon=23.3,
        property_type="house",
        area_sqm=120.0,
    )
    assert vec[3] == -1  # floor missing
    assert vec[4] == -1  # rooms missing
    assert vec[5] == -1  # bedrooms missing
    assert vec[6] == -1  # year_built missing


def test_build_feature_vector_one_hot():
    vec = build_feature_vector(
        lat=35.0,
        lon=14.0,
        property_type="villa",
        area_sqm=200.0,
        condition="new",
    )
    # villa is index 2 in PROPERTY_TYPES, so type_villa should be 1.0
    type_start = 7  # after lat, lon, area, floor, rooms, bedrooms, year
    assert vec[type_start + 0] == 0.0  # apartment
    assert vec[type_start + 1] == 0.0  # house
    assert vec[type_start + 2] == 1.0  # villa

    cond_start = type_start + 6  # 6 property types
    assert vec[cond_start + 0] == 1.0  # new
    assert vec[cond_start + 1] == 0.0  # excellent
