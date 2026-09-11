import pandas as pd
import pytest
from model_predict import build_feature_vector

FEATURE_NAMES = [
    "DURATION_SECONDS",
    "PUBLISHED_HOUR",
    "TITLE_LENGTH",
    "TITLE_WORD_COUNT",
    "TITLE_HAS_NUMBER",
    "TITLE_HAS_QUESTION",
    "TITLE_CAPS_RATIO",
    "PUBLISHED_WEEKDAY_Friday",
    "PUBLISHED_WEEKDAY_Monday",
    "PUBLISHED_WEEKDAY_Saturday",
    "PUBLISHED_WEEKDAY_Sunday",
    "PUBLISHED_WEEKDAY_Thursday",
    "PUBLISHED_WEEKDAY_Tuesday",
    "PUBLISHED_WEEKDAY_Wednesday",
    "CATEGORY_ID_10",
    "CATEGORY_ID_20",
    "CATEGORY_ID_22",
    "CATEGORY_ID_24",
    "CATEGORY_ID_25",
    "CATEGORY_ID_26",
    "CATEGORY_ID_27",
    "CATEGORY_ID_28",
    "CATEGORY_ID_29",
    "CATEGORY_ID_2",
]


def _build(**kwargs):
    defaults = dict(
        duration_seconds=300,
        published_weekday="Friday",
        category_id="22",
        title="Test Video",
        published_hour=15,
    )
    defaults.update(kwargs)
    return build_feature_vector(**defaults, feature_names=FEATURE_NAMES)


def test_output_has_24_features():
    fv = _build()
    assert fv.shape == (1, 24)


def test_weekday_one_hot_friday():
    fv = _build(published_weekday="Friday")
    assert fv["PUBLISHED_WEEKDAY_Friday"].iloc[0] == 1
    for col in [c for c in FEATURE_NAMES if c.startswith("PUBLISHED_WEEKDAY_") and c != "PUBLISHED_WEEKDAY_Friday"]:
        assert fv[col].iloc[0] == 0


def test_weekday_one_hot_tuesday():
    fv = _build(published_weekday="Tuesday")
    assert fv["PUBLISHED_WEEKDAY_Tuesday"].iloc[0] == 1
    for col in [c for c in FEATURE_NAMES if c.startswith("PUBLISHED_WEEKDAY_") and c != "PUBLISHED_WEEKDAY_Tuesday"]:
        assert fv[col].iloc[0] == 0


def test_category_one_hot():
    fv = _build(category_id="20")
    assert fv["CATEGORY_ID_20"].iloc[0] == 1
    for col in [c for c in FEATURE_NAMES if c.startswith("CATEGORY_ID_") and c != "CATEGORY_ID_20"]:
        assert fv[col].iloc[0] == 0


def test_duration_and_hour_pass_through():
    fv = _build(duration_seconds=600, published_hour=18)
    assert fv["DURATION_SECONDS"].iloc[0] == 600
    assert fv["PUBLISHED_HOUR"].iloc[0] == 18


def test_title_length():
    fv = _build(title="Hello World")
    assert fv["TITLE_LENGTH"].iloc[0] == len("Hello World")


def test_title_word_count():
    fv = _build(title="One Two Three Four")
    assert fv["TITLE_WORD_COUNT"].iloc[0] == 4


def test_title_has_number_true():
    fv = _build(title="Top 10 Fails")
    assert fv["TITLE_HAS_NUMBER"].iloc[0] == 1


def test_title_has_number_false():
    fv = _build(title="No Numbers Here")
    assert fv["TITLE_HAS_NUMBER"].iloc[0] == 0


def test_title_has_question_true():
    fv = _build(title="Is this real?")
    assert fv["TITLE_HAS_QUESTION"].iloc[0] == 1


def test_title_has_question_false():
    fv = _build(title="This is real")
    assert fv["TITLE_HAS_QUESTION"].iloc[0] == 0


def test_caps_ratio_all_caps():
    fv = _build(title="ABC")
    assert fv["TITLE_CAPS_RATIO"].iloc[0] == pytest.approx(1.0)


def test_caps_ratio_no_caps():
    fv = _build(title="abc")
    assert fv["TITLE_CAPS_RATIO"].iloc[0] == pytest.approx(0.0)
