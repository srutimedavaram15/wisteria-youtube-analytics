"""
Trains a model using Snowpark ML on MODELING.VIDEOS_TRAINING_DATA.
"""

import os

import pandas as pd
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from snowflake.snowpark import Session

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


def add_performance_tier(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds PERFORMANCE_TIER to each video based on where its VIEW_COUNT falls
    relative to its own channel's 33rd/67th percentile cutoffs.
    """
    p33 = df.groupby("SOURCE_CHANNEL_ID")["VIEW_COUNT"].transform(
        lambda x: x.quantile(0.33)
    )
    p67 = df.groupby("SOURCE_CHANNEL_ID")["VIEW_COUNT"].transform(
        lambda x: x.quantile(0.67)
    )
    df = df.copy()
    df["PERFORMANCE_TIER"] = "typical"
    df.loc[df["VIEW_COUNT"] < p33, "PERFORMANCE_TIER"] = "below_average"
    df.loc[df["VIEW_COUNT"] > p67, "PERFORMANCE_TIER"] = "above_average"
    return df


def add_title_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds numeric features derived from the TITLE column."""
    t = df["TITLE"].fillna("")
    alpha_chars = t.apply(lambda s: sum(c.isalpha() for c in s))
    upper_chars = t.apply(lambda s: sum(c.isupper() for c in s))

    df = df.copy()
    df["TITLE_LENGTH"]    = t.str.len()
    df["TITLE_WORD_COUNT"] = t.str.split().str.len().fillna(0).astype(int)
    df["TITLE_HAS_NUMBER"]   = t.str.contains(r"\d", regex=True).astype(int)
    df["TITLE_HAS_QUESTION"] = t.str.contains("?", regex=False).astype(int)
    df["TITLE_CAPS_RATIO"]   = upper_chars.where(alpha_chars > 0, 0) / alpha_chars.where(alpha_chars > 0, 1)
    return df


def prepare_features(df):
    """
    Converts a Snowpark DataFrame to pandas, encodes categorical columns,
    and returns an 80/20 train/test split.
    """
    pdf = df.to_pandas()
    pdf = add_performance_tier(pdf)
    pdf = add_title_features(pdf)

    pdf = pd.get_dummies(pdf, columns=["PUBLISHED_WEEKDAY", "CATEGORY_ID"])

    weekday_cols = [c for c in pdf.columns if c.startswith("PUBLISHED_WEEKDAY_")]
    category_cols = [c for c in pdf.columns if c.startswith("CATEGORY_ID_")]
    title_cols = [
        "TITLE_LENGTH", "TITLE_WORD_COUNT", "TITLE_HAS_NUMBER",
        "TITLE_HAS_QUESTION", "TITLE_CAPS_RATIO",
    ]
    feature_cols = ["DURATION_SECONDS", "PUBLISHED_HOUR"] + title_cols + weekday_cols + category_cols

    X = pdf[feature_cols]
    y = pdf["PERFORMANCE_TIER"]

    return train_test_split(X, y, test_size=0.2, random_state=42)


def train_and_evaluate(X_train, X_test, y_train, y_test):
    """Trains a RandomForestClassifier and reports accuracy + per-tier metrics."""
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)

    print(f"Accuracy: {accuracy:.4f}")
    print(classification_report(y_test, predictions))

    return model


def tune_and_evaluate(X_train, X_test, y_train, y_test):
    """
    Searches hyperparameters via RandomizedSearchCV (training data only),
    then evaluates the best estimator once against the held-out test set.
    """
    param_dist = {
        "n_estimators":      [100, 200, 300, 400],
        "max_depth":         [None, 10, 20, 30],
        "min_samples_split": [2, 5, 10],
        "min_samples_leaf":  [1, 2, 4],
        "max_features":      ["sqrt", "log2"],
    }

    search = RandomizedSearchCV(
        RandomForestClassifier(random_state=42),
        param_distributions=param_dist,
        n_iter=20,
        cv=5,
        scoring="accuracy",
        random_state=42,
        n_jobs=-1,
    )
    search.fit(X_train, y_train)

    print(f"Best CV accuracy: {search.best_score_:.4f}")
    print(f"Best params:      {search.best_params_}")

    best_model = search.best_estimator_
    predictions = best_model.predict(X_test)
    print(f"\nTest accuracy: {accuracy_score(y_test, predictions):.4f}")
    print(classification_report(y_test, predictions))

    return best_model


def register_model(session, model, X_test) -> None:
    """Logs the trained model to the Snowflake Model Registry."""
    from snowflake.ml.registry import Registry

    registry = Registry(
        session=session,
        database_name="YT_ANALYTICS",
        schema_name="MODELING",
    )
    registry.log_model(
        model,
        model_name="video_performance_tier_predictor",
        version_name="v1",
        sample_input_data=X_test.head(5),
        comment=(
            "RandomForestClassifier predicting performance tier from "
            "duration, category, timing, and title features. "
            "Trained on SSSniperWolf public data as a stand-in dataset."
        ),
    )
    print("Model registered: video_performance_tier_predictor v1")


def main() -> None:
    session = get_session()
    try:
        df = session.table("VIDEOS_TRAINING_DATA")
        print(f"Row count: {df.count()}")
        df.show(5)

        X_train, X_test, y_train, y_test = prepare_features(df)
        print(f"X_train shape: {X_train.shape}")
        print(f"X_test shape:  {X_test.shape}")

        best_model = tune_and_evaluate(X_train, X_test, y_train, y_test)

        print("\nTest set tier distribution:")
        print(y_test.value_counts().to_string())

        register_model(session, best_model, X_test)
    finally:
        session.close()


if __name__ == "__main__":
    main()
