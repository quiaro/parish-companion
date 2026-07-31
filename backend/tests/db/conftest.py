import pytest
from sqlalchemy import text

from db.engine import engine


@pytest.fixture(autouse=True)
def _truncate_tables():
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE comfort_sent_passages, parishioners, comfort_aggregate_stats RESTART IDENTITY CASCADE"
            )
        )
    yield
