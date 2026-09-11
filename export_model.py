"""
Downloads the registered model from Snowflake and saves it as a local pickle.
Run with: python export_model.py
"""

from model_predict import export_model_locally, get_session

OUTPUT_PATH = "model.pkl"

if __name__ == "__main__":
    session = get_session()
    try:
        export_model_locally(session, OUTPUT_PATH)
        print(f"Model saved to {OUTPUT_PATH}")
    finally:
        session.close()
