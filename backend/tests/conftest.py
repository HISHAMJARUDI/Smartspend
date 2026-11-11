import os

from app.database import engine


def pytest_sessionstart(session):
    if os.environ.get("SMARTSPEND_TEST_MODE") != "1":
        raise RuntimeError(
            "Use python -m scripts.run_tests"
        )

    if engine.url.database != "smartspend_test":
        raise RuntimeError(
            "REFUSING TO TEST NON-TEST DATABASE"
        )

    print(
        "\nDatabase safety verified: smartspend_test"
    )
