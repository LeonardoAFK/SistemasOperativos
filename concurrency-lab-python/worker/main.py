import fcntl
import os
import random
import socket
import time
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "concurrency_lab"),
    "user": os.getenv("DB_USER", "lab_user"),
    "password": os.getenv("DB_PASSWORD", "lab_password"),
}

WORKER_IDENTIFIER = os.getenv("WORKER_IDENTIFIER") or socket.gethostname()
SHARED_LOG_FILE = os.getenv("SHARED_LOG_FILE", "/shared/worker-log.txt")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def write_shared_log(message: str) -> None:
    """
    Writes to a shared file using an exclusive file lock.

    This prevents several containers from writing mixed or corrupted lines
    at the same time.
    """
    os.makedirs(os.path.dirname(SHARED_LOG_FILE), exist_ok=True)

    with open(SHARED_LOG_FILE, "a", encoding="utf-8") as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        try:
            file.write(f"{utc_now_iso()} | {WORKER_IDENTIFIER} | {message}\n")
            file.flush()
            os.fsync(file.fileno())
        finally:
            fcntl.flock(file, fcntl.LOCK_UN)


@contextmanager
def get_connection():
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        yield connection
    finally:
        connection.close()


def wait_for_database(max_attempts: int = 20) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1;")
            return
        except Exception as error:
            print(
                f"[{WORKER_IDENTIFIER}] Database not ready "
                f"(attempt {attempt}/{max_attempts}): {error}"
            )
            time.sleep(1)

    raise RuntimeError("Database connection could not be established.")


def claim_next_input(connection):
    """
    Claims one pending input row in a transaction.

    FOR UPDATE SKIP LOCKED is the key mechanism:
    - FOR UPDATE locks the selected row.
    - SKIP LOCKED avoids waiting for rows already locked by other workers.
    - This allows each worker to receive a different pending row.
    """
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("BEGIN;")

        cursor.execute(
            """
            SELECT id, description
            FROM input
            WHERE status = 'pending'
            ORDER BY id
            LIMIT 1
            FOR UPDATE SKIP LOCKED;
            """
        )

        row = cursor.fetchone()

        if row is None:
            cursor.execute("COMMIT;")
            return None

        cursor.execute(
            """
            UPDATE input
            SET status = 'in_process',
                worker_identifier = %s,
                in_process_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (WORKER_IDENTIFIER, row["id"]),
        )

        cursor.execute("COMMIT;")
        return row


def process_input(row) -> str:
    """
    Simulates independent processing.

    The random sleep makes the concurrent behavior easier to observe because
    workers will finish tasks at different times.
    """
    processing_seconds = random.uniform(0.5, 2.5)

    write_shared_log(
        f"START input_id={row['id']} description='{row['description']}' "
        f"estimated_seconds={processing_seconds:.2f}"
    )

    time.sleep(processing_seconds)

    processed_text = row["description"].upper()
    return f"Processed by {WORKER_IDENTIFIER}: {processed_text}"


def save_result(connection, input_id: int, result_text: str) -> bool:
    """
    Saves the result and marks the input as processed.

    The result table has UNIQUE(input_id), so even if a bug appears in the
    worker logic, the database protects us from duplicate results.
    """
    with connection.cursor() as cursor:
        cursor.execute("BEGIN;")

        cursor.execute(
            """
            INSERT INTO result (input_id, worker_identifier, result)
            VALUES (%s, %s, %s)
            ON CONFLICT (input_id) DO NOTHING
            RETURNING id;
            """,
            (input_id, WORKER_IDENTIFIER, result_text),
        )

        inserted_row = cursor.fetchone()

        if inserted_row is None:
            cursor.execute("ROLLBACK;")
            write_shared_log(
                f"WARNING duplicate result ignored for input_id={input_id}"
            )
            return False

        cursor.execute(
            """
            UPDATE input
            SET status = 'processed',
                processed_at = CURRENT_TIMESTAMP
            WHERE id = %s;
            """,
            (input_id,),
        )

        cursor.execute("COMMIT;")
        return True


def main() -> None:
    print(f"[{WORKER_IDENTIFIER}] Worker started.")
    write_shared_log("Worker started")

    wait_for_database()

    processed_count = 0

    with get_connection() as connection:
        connection.autocommit = False

        while True:
            row = claim_next_input(connection)

            if row is None:
                write_shared_log("No pending inputs found. Worker finished.")
                break

            result_text = process_input(row)
            was_saved = save_result(connection, row["id"], result_text)

            if was_saved:
                processed_count += 1
                write_shared_log(f"FINISH input_id={row['id']} result_saved=true")
                print(
                    f"[{WORKER_IDENTIFIER}] Processed input_id={row['id']}"
                )

    write_shared_log(f"Worker stopped. processed_count={processed_count}")
    print(f"[{WORKER_IDENTIFIER}] Worker stopped. processed_count={processed_count}")


if __name__ == "__main__":
    main()
