import pytest
from sqlalchemy import text

from db.engine import engine


@pytest.fixture(autouse=True)
def _truncate_tables():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE comfort_sent_passages, parishioners RESTART IDENTITY CASCADE"))
    yield
