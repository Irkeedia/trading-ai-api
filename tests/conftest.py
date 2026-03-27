import os

# Avant l'import de `src.api.main` (CORS lit EnvSettings au chargement du module).
os.environ["DATABASE_URL"] = os.environ.get(
    "PYTEST_DATABASE_URL", "postgresql://127.0.0.1:59999/trading_pytest_db"
)
os.environ["API_SECRET_KEY"] = "pytest-api-secret-not-for-prod"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.api.main import app

    with TestClient(app) as c:
        yield c
