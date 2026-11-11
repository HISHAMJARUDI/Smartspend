import os
import subprocess
import sys

from sqlalchemy.engine import make_url

from app.database import settings


url = make_url(settings.DATABASE_URL)

if url.get_backend_name() != "postgresql":
    raise SystemExit("PostgreSQL required")

if url.database not in (
    "smartspend_db",
    "smartspend_test",
):
    raise SystemExit("Unexpected database configuration")

test_url = url.set(database="smartspend_test")

env = os.environ.copy()
env["DATABASE_URL"] = test_url.render_as_string(
    hide_password=False
)
env["SMARTSPEND_TEST_MODE"] = "1"
env["DEMO_POS_ENABLED"] = "true"

print("Running tests against smartspend_test only")

result = subprocess.run(
    [sys.executable, "-m", "pytest", "-v", "tests"],
    env=env,
)

sys.exit(result.returncode)
