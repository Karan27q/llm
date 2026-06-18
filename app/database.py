import os
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker, declarative_base
from app.config import Config

db_url = Config.DATABASE_URL
if not db_url:
    db_url = "sqlite:///chat_history.db"

def try_connect(url: str) -> bool:
    """Helper to test database connection readability."""
    if url.startswith("sqlite"):
        return True
    try:
        import psycopg2
        # Set a short timeout of 3 seconds to test connectivity
        conn = psycopg2.connect(url, connect_timeout=3)
        conn.close()
        return True
    except Exception as e:
        print(f"Warning: Database connection to {url} failed: {e}")
        return False

# Fall back to SQLite if the configured database is unreachable
if not try_connect(db_url):
    print("Falling back to local SQLite database: chat_history.db")
    db_url = "sqlite:///chat_history.db"

# Create engine
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True if not db_url.startswith("sqlite") else False)
except Exception as e:
    print(f"Warning: Failed to initialize database engine for URL: {db_url}. Falling back to SQLite.")
    db_url = "sqlite:///chat_history.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    # Import models to register with Base metadata
    import app.models.user
    import app.models.conversation
    import app.models.message
    import app.models.audit_log

    # Programmatically run Alembic migrations
    import os
    from alembic.config import Config as AlembicConfig
    from alembic import command

    # Locate alembic.ini relative to this file
    ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    alembic_cfg = AlembicConfig(ini_path)
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    try:
        command.upgrade(alembic_cfg, "head")
        print("Database migrations applied successfully via Alembic.")
    except Exception as e:
        print(f"Warning: Programmatic Alembic upgrade failed: {e}. Falling back to metadata.create_all.")
        Base.metadata.create_all(bind=engine)
