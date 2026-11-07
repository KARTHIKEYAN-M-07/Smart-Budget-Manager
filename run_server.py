"""Smart Family Budget Manager - Local Server Runner

Initializes persistent local SQLite database, sets up schema, and starts Uvicorn.
Open http://127.0.0.1:8000/docs in your browser to interact with the API!
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

# Configure persistent SQLite database for local run
db_file = Path(__file__).resolve().parent / "sfbm_local.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file.as_posix()}"
os.environ["DATABASE_SYNC_URL"] = f"sqlite:///{db_file.as_posix()}"
os.environ["ENVIRONMENT"] = "development"
os.environ["DEBUG"] = "true"

from app.core.database import engine
from app.models import Base


async def init_db():
    print("[1/2] Initializing database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"[2/2] Database ready at: {db_file}")


if __name__ == "__main__":
    asyncio.run(init_db())
    import uvicorn

    print("\n" + "=" * 65)
    print("  Smart Family Budget Manager is running!")
    print("  API Server:  http://127.0.0.1:8000")
    print("  Swagger UI:  http://127.0.0.1:8000/docs")
    print("  Health:      http://127.0.0.1:8000/api/v1/health")
    print("=" * 65 + "\n")

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
