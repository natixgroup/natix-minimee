"""
Verify pgvector extension is installed in PostgreSQL
"""
import psycopg2
import sys
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def check_pgvector(database_url: str) -> bool:
    """
    Check if pgvector extension is installed.
    Raises RuntimeError if not found.
    """
    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Check if pgvector extension exists
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector');"
        )
        exists = cursor.fetchone()[0]

        if not exists:
            # Try to create it
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector');"
                )
                exists = cursor.fetchone()[0]
            except Exception as create_error:
                raise RuntimeError(
                    f"pgvector extension not found and could not be created: {create_error}"
                )

        cursor.close()
        conn.close()

        if not exists:
            raise RuntimeError(
                "pgvector extension is not installed. "
                "Please install it: CREATE EXTENSION vector;"
            )

        return True

    except psycopg2.OperationalError as e:
        raise RuntimeError(
            f"Could not connect to database to check pgvector: {e}"
        )
    except Exception as e:
        raise RuntimeError(f"Error checking pgvector: {e}")


if __name__ == "__main__":
    import os
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://minimee:minimee@localhost:5432/minimee"
    )
    try:
        check_pgvector(database_url)
        print("✓ pgvector extension verified")
    except RuntimeError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)

