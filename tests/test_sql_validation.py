import pytest
from llm_query import validate_sql

CHANNEL_ID = "UCpB959t8iPrxQWj7G6n0ctQ"
SAFE_SQL = f"SELECT * FROM RAW.VIDEOS WHERE CHANNEL_ID = '{CHANNEL_ID}'"


def test_safe_select_passes():
    assert validate_sql(SAFE_SQL, CHANNEL_ID) is True


@pytest.mark.parametrize("keyword", ["DROP", "DELETE", "ALTER", "CREATE"])
def test_write_keywords_are_rejected(keyword):
    sql = f"{keyword} TABLE RAW.VIDEOS; SELECT * FROM RAW.VIDEOS WHERE CHANNEL_ID = '{CHANNEL_ID}'"
    assert validate_sql(sql, CHANNEL_ID) is False


def test_missing_channel_filter_is_rejected():
    sql = "SELECT * FROM RAW.VIDEOS"
    assert validate_sql(sql, CHANNEL_ID) is False


def test_column_name_with_create_substring_is_not_flagged():
    # "created_at" contains "create" but should not trigger the CREATE keyword check
    sql = f"SELECT created_at FROM RAW.VIDEOS WHERE CHANNEL_ID = '{CHANNEL_ID}'"
    assert validate_sql(sql, CHANNEL_ID) is True


def test_column_name_with_drop_substring_is_not_flagged():
    # "raindrop" contains "drop" but should not trigger the DROP keyword check
    sql = f"SELECT raindrop FROM RAW.VIDEOS WHERE CHANNEL_ID = '{CHANNEL_ID}'"
    assert validate_sql(sql, CHANNEL_ID) is True


def test_non_select_statement_is_rejected():
    sql = f"INSERT INTO RAW.VIDEOS (CHANNEL_ID) VALUES ('{CHANNEL_ID}')"
    assert validate_sql(sql, CHANNEL_ID) is False
