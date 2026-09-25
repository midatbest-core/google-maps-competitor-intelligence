import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base

# Try to use SQLite for tests if Postgres is unavailable, 
# but note that pgvector features will not work on SQLite natively.
# For demonstration in restricted environments, we'll use in-memory sqlite.
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def db_engine():
    # Attempt to create tables. This might fail if using sqlite + pgvector.
    # In a real environment, this should connect to a test postgres DB.
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Failed to create schema in test DB: {e}")
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()
