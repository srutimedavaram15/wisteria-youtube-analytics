import re
from dotenv import load_dotenv
from app_router import get_session

load_dotenv(dotenv_path=".env")

sql = open("demo_views.sql").read()
statements = [s.strip() for s in re.split(r';\s*\n', sql) if s.strip()]

session = get_session()
try:
    for stmt in statements:
        view_name = re.search(r'VIEW\s+(\S+)', stmt, re.IGNORECASE).group(1)
        session.sql(stmt).collect()
        print(f"Created view: {view_name}")
finally:
    session.close()
