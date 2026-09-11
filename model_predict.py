"""
Loads the registered video performance tier model from Snowflake Model Registry.
"""

import os

import joblib
import pandas as pd
from dotenv import load_dotenv
from snowflake.ml.registry import Registry
from snowflake.snowpark import Session

from train_model import add_title_features

load_dotenv()


def get_session() -> Session:
    return Session.builder.configs({
        "account":   os.environ["SNOWFLAKE_ACCOUNT"],
        "user":      os.environ["SNOWFLAKE_USER"],
        "password":  os.environ["SNOWFLAKE_PASSWORD"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database":  os.environ["SNOWFLAKE_DATABASE"],
        "schema":    "MODELING",
    }).create()


def load_model(session: Session):
    """
    Retrieves the video_performance_tier_predictor v1 from the Model Registry
    and returns it as a usable Python object.
    """
    registry = Registry(
        session=session,
        database_name="YT_ANALYTICS",
        schema_name="MODELING",
    )
    model_version = registry.get_model("video_performance_tier_predictor").version("v1")
    return model_version.load()


def build_feature_vector(
    duration_seconds: int,
    published_weekday: str,
    category_id: str,
    title: str,
    published_hour: int,
    feature_names,
) -> pd.DataFrame:
    """
    Builds a single-row DataFrame whose columns exactly match feature_names,
    in the same order, ready to pass directly to model.predict().
    """
    tmp = add_title_features(pd.DataFrame([{"TITLE": title}]))
    title_row = tmp.iloc[0]

    row = {}
    for col in feature_names:
        if col == "DURATION_SECONDS":
            row[col] = duration_seconds
        elif col == "PUBLISHED_HOUR":
            row[col] = published_hour
        elif col in ("TITLE_LENGTH", "TITLE_WORD_COUNT", "TITLE_HAS_NUMBER",
                     "TITLE_HAS_QUESTION", "TITLE_CAPS_RATIO"):
            row[col] = title_row[col]
        elif col.startswith("PUBLISHED_WEEKDAY_"):
            row[col] = 1 if col == f"PUBLISHED_WEEKDAY_{published_weekday}" else 0
        elif col.startswith("CATEGORY_ID_"):
            row[col] = 1 if col == f"CATEGORY_ID_{category_id}" else 0
        else:
            row[col] = 0

    return pd.DataFrame([row])[list(feature_names)]


def predict_tier(model, feature_vector: pd.DataFrame) -> str:
    """Returns the predicted performance tier label as a plain string."""
    return str(model.predict(feature_vector)[0])


def main() -> None:
    session = get_session()
    try:
        model = load_model(session)
        if hasattr(model, "feature_names_in_"):
            print("Feature names expected by the model:")
            for name in model.feature_names_in_:
                print(f"  {name}")
        else:
            print("model.feature_names_in_ is not available on this model object.")
            print(f"Model type: {type(model)}")

        fv = build_feature_vector(
            duration_seconds=600,
            published_weekday="Friday",
            category_id="22",
            title="I Tried This Viral Hack",
            published_hour=18,
            feature_names=model.feature_names_in_,
        )
        tier = predict_tier(model, fv)
        print(f"\nPredicted performance tier: {tier}")
    finally:
        session.close()


def export_model_locally(session: Session, output_path: str) -> None:
    """Downloads the registered model and saves it as a local pickle file."""
    model = load_model(session)
    joblib.dump(model, output_path)


if __name__ == "__main__":
    main()
