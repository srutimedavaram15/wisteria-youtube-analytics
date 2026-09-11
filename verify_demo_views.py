from dotenv import load_dotenv
from app_router import get_session

load_dotenv(dotenv_path=".env")

VIEWS = [
    "MODELING.DEMO_PERFORMANCE_BY_WEEKDAY",
    "MODELING.DEMO_PERFORMANCE_BY_CATEGORY",
    "MODELING.DEMO_TITLE_LENGTH_VS_VIEWS",
    "MODELING.DEMO_KPI_SUMMARY",
]

session = get_session()
try:
    for view in VIEWS:
        print(f"\n=== {view} ===")
        rows = session.sql(f"SELECT * FROM {view} LIMIT 5").collect()
        for row in rows:
            print(row.as_dict())
finally:
    session.close()
