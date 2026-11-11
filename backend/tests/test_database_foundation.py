from sqlalchemy import inspect, text

from app.database import engine, Base
import app.models


def test_database_is_isolated():
    with engine.connect() as connection:
        name = connection.scalar(
            text("SELECT current_database()")
        )

    assert name == "smartspend_test"


def test_all_model_tables_exist():
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    expected = set(Base.metadata.tables.keys())

    missing = expected - existing

    assert not missing, (
        f"Missing database tables: {missing}"
    )


def test_only_one_active_card_allowed():
    with engine.connect() as connection:
        index = connection.scalar(
            text("""
                SELECT indexdef
                FROM pg_indexes
                WHERE tablename = 'cards'
                  AND indexname =
                  'uq_cards_one_active_per_student'
            """)
        )

    assert index is not None
    assert "UNIQUE INDEX" in index.upper()
    assert "student_id" in index
    assert "WHERE" in index.upper()
    assert "active" in index


def test_financial_ledger_foreign_keys_exist():
    inspector = inspect(engine)

    entry_keys = inspector.get_foreign_keys(
        "ledger_entries"
    )

    references = {
        key["referred_table"]
        for key in entry_keys
    }

    assert "transactions" in references
    assert "ledger_accounts" in references
