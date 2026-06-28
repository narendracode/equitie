import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://equitie:equitie@localhost:5432/equitie",
)


@pytest.fixture(scope="session")
def db():
    """Session-scoped SQLAlchemy session against the live seeded database.

    Override DATABASE_URL env var to point at a different host.
    Default: localhost:5432 (Docker port-forwarding).
    """
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.exit(
            f"\n\nCannot connect to database at {DATABASE_URL}\n"
            f"Make sure Docker is running: make up-d\n"
            f"Error: {exc}",
            returncode=1,
        )

    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()
