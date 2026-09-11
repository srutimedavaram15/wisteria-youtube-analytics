"""
Translates a creator's natural-language question into a SQL SELECT statement
using Claude, scoped to their channel and the RAW schema tables/views.
"""

import os
import re
import sys

import anthropic
from dotenv import load_dotenv
from snowflake.snowpark import Session

load_dotenv()

SCHEMA_CONTEXT = """
You have access to the following tables and views in the RAW schema of the YT_ANALYTICS database:

TABLE: VIDEOS
  VIDEO_ID          VARCHAR  -- unique YouTube video ID
  CHANNEL_ID        VARCHAR  -- the creator's channel ID
  TITLE             VARCHAR  -- video title
  PUBLISHED_AT      TIMESTAMP_NTZ
  PUBLISHED_WEEKDAY VARCHAR  -- e.g. 'Monday', 'Tuesday', ...
  PUBLISHED_HOUR    INTEGER  -- hour of day (0–23, UTC)
  DURATION_SECONDS  INTEGER
  CATEGORY_ID       VARCHAR  -- YouTube category ID (e.g. '22' for People & Blogs)
  VIEW_COUNT        INTEGER
  LIKE_COUNT        INTEGER
  COMMENT_COUNT     INTEGER

VIEW: VIDEOS_WITH_CATEGORY_NAMES
  (all columns from VIDEOS, plus:)
  CATEGORY_NAME     VARCHAR  -- human-readable category (e.g. 'Gaming', 'Entertainment')
  Use this view instead of VIDEOS whenever the question relates to video category,
  so you can filter or group by CATEGORY_NAME rather than the raw CATEGORY_ID.

TABLE: VIDEO_DAILY_STATS
  CHANNEL_ID                VARCHAR
  VIDEO_ID                  VARCHAR
  STAT_DATE                 DATE
  VIEWS                     INTEGER  -- views on that specific day
  LIKES                     INTEGER
  COMMENTS                  INTEGER
  ESTIMATED_MINUTES_WATCHED FLOAT
  AVERAGE_VIEW_DURATION     FLOAT    -- seconds

VIEW: PERFORMANCE_BY_WEEKDAY
  CHANNEL_ID              VARCHAR
  PUBLISHED_WEEKDAY       VARCHAR
  NUM_VIDEOS              NUMBER
  AVG_LIFETIME_VIEWS      NUMBER
  AVG_LIFETIME_LIKES      NUMBER
  AVG_LIFETIME_COMMENTS   NUMBER

VIEW: VIDEO_PERFORMANCE_VS_BASELINE
  VIDEO_ID               VARCHAR
  CHANNEL_ID             VARCHAR
  TITLE                  VARCHAR
  VIEW_COUNT             NUMBER
  NUM_COMPARISON_VIDEOS  NUMBER
  CHANNEL_AVG_EXCL_SELF  NUMBER  -- NULL if NUM_COMPARISON_VIDEOS is 0
  PERFORMANCE_RATIO      NUMBER  -- NULL if not enough data to compare

VIEW: BEST_DAY_TO_POST
  CHANNEL_ID             VARCHAR  -- one row per channel, not per weekday
  BEST_WEEKDAY           VARCHAR  -- NULL if HAS_SUFFICIENT_DATA is false
  BEST_WEEKDAY_AVG_VIEWS NUMBER   -- NULL if HAS_SUFFICIENT_DATA is false
  HAS_SUFFICIENT_DATA    BOOLEAN
"""

_SYSTEM_PROMPT = f"""\
You are a SQL assistant for a YouTube analytics application.
Given a creator's question, write a single SELECT statement that answers it.

{SCHEMA_CONTEXT}

Rules:
- Return ONLY the raw SQL — no explanation, no markdown, no code fences.
- Write exactly one SELECT statement. Never write INSERT, UPDATE, DELETE, DROP, ALTER, or CREATE.
- Every query MUST include a WHERE CHANNEL_ID = '<channel_id>' filter
  (replace <channel_id> with the actual channel ID provided in the instruction).
- All table and view names are in the RAW schema; qualify them as RAW.<table>.
- Use standard SQL compatible with Snowflake.
- If the question cannot be answered with the available schema (for example, comparing
  against other creators, data from other platforms, or anything not covered by these
  tables), respond with exactly the text NO_SQL_POSSIBLE instead of attempting a query.
"""


def generate_sql(question: str, channel_id: str) -> str:
    """
    Sends the creator's question to Claude and returns a raw SQL SELECT string.
    """
    system = _SYSTEM_PROMPT.replace("<channel_id>", channel_id)
    user_message = (
        f"Channel ID: {channel_id}\n\nQuestion: {question}"
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text.strip()


_FORBIDDEN_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "CREATE", "TRUNCATE", "GRANT", "REVOKE",
}


def validate_sql(sql: str, channel_id: str) -> bool:
    """
    Returns True only if the SQL is a safe, channel-scoped SELECT statement.
    Checks: starts with SELECT, contains no write/DDL keywords, and includes
    a CHANNEL_ID filter for the given channel_id.
    """
    stripped = sql.strip()

    if not stripped.upper().startswith("SELECT"):
        return False

    for keyword in _FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", stripped, re.IGNORECASE):
            return False

    escaped = re.escape(channel_id)
    if not re.search(
        rf"CHANNEL_ID\s*=\s*(?:'{escaped}'|\"{escaped}\")",
        stripped,
        re.IGNORECASE,
    ):
        return False

    return True


def get_session() -> Session:
    return Session.builder.configs({
        "account":   os.environ["SNOWFLAKE_ACCOUNT"],
        "user":      os.environ["SNOWFLAKE_USER"],
        "password":  os.environ["SNOWFLAKE_PASSWORD"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database":  os.environ["SNOWFLAKE_DATABASE"],
        "schema":    "RAW",
    }).create()


def execute_and_answer(question: str, channel_id: str, session: Session) -> str:
    """
    Generates SQL for the question, validates it, executes it, and returns
    a plain-English answer summarizing the results.
    """
    sql = generate_sql(question, channel_id)

    if sql == "NO_SQL_POSSIBLE":
        return "🌸 I don't have that information yet, but I can help with things like your best day to post, video performance, category breakdowns, and more!"

    if not validate_sql(sql, channel_id):
        print(f"[REJECTED SQL]\n{sql}", file=sys.stderr)
        return "Sorry, I couldn't safely answer that question. Please try rephrasing it."

    rows = session.sql(sql).collect()

    results_text = "\n".join(str(row) for row in rows) if rows else "(no rows returned)"

    summary_prompt = (
        f"A YouTube creator asked: \"{question}\"\n\n"
        f"The following SQL was run to answer it:\n{sql}\n\n"
        f"Results:\n{results_text}\n\n"
        "Summarize the answer in 1-3 sentences of plain English, directly addressing "
        "the creator's question. If the results are empty or contain only NULLs, "
        "explain that there isn't enough data to answer yet — don't invent an answer. "
        "Respond in plain, conversational text only — no markdown formatting, no headers, "
        "no asterisks for bold, no bullet points. Just natural sentences. "
        "If the data includes DURATION_SECONDS, convert it to a natural format like "
        "'X minutes Y seconds' rather than stating raw seconds. "
        "If it includes PUBLISHED_HOUR (0-23), convert it to 12-hour format with AM/PM "
        "(e.g., 15 becomes '3 PM') rather than stating the raw hour number."
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": summary_prompt}],
    )
    return response.content[0].text.strip()


def main() -> None:
    channel_id = "UC_5MDffbru8OYck3HCTUoIw"
    session = get_session()
    try:
        answer = execute_and_answer(
            question="What's my best day to post?",
            channel_id=channel_id,
            session=session,
        )
        print(answer)
    finally:
        session.close()


if __name__ == "__main__":
    main()
