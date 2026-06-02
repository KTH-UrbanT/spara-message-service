from dataclasses import dataclass
import json
from typing import Any, Optional
import os

import psycopg2
from psycopg2.extras import Json
from psycopg2 import sql


@dataclass
class User:
    user_id: int
    username: str
    email: str
    password: str
    created_at: str
    last_logged_in: str


@dataclass
class Session:
    session_id: int
    user_id: int
    session_token: str
    is_active: bool
    created_at: str
    last_accessed: str


@dataclass
class Message:
    message_id: int
    session_id: int
    role: str
    content: str
    sent_at: str
    metadata: Optional[dict] = None
    rating_id: Optional[int] = None
    rating: Optional[float] = None
    version: Optional[str] = None


ALLOWED_USER_COLUMNS = {"user_id", "username", "email"}
ALLOWED_SESSION_COLUMNS = {"session_id", "user_id", "session_token"}
ALLOWED_MESSAGE_COLUMNS = {"message_id", "session_id", "sender_id"}
VALID_MESSAGE_ROLES = {"user", "assistant", "system"}
_MESSAGE_OBSERVABILITY_SCHEMA_READY: Optional[bool] = None

ADVISOR_REVIEW_BOOLEAN_FIELDS = (
    "route_correct",
    "building_data_correct",
    "recommendation_correct",
    "personalized",
    "useful",
    "too_generic",
    "needs_minor_edit",
    "needs_major_edit",
    "unsafe_or_misleading",
    "should_have_asked_clarification",
    "should_have_escalated",
)

ADVISOR_REVIEW_SCORE_FIELDS = (
    "technical_correctness_score",
    "building_specificity_score",
    "personalization_score",
    "usefulness_score",
    "justification_score",
    "clarity_score",
    "trust_score",
    "safety_score",
    "advisor_confidence",
)

ADVISOR_REVIEW_CORRECTION_FIELDS = (
    "correction_actions",
    "corrected_answer",
    "correction_summary",
)


def get_connection():
    return psycopg2.connect(
        host=os.environ["SQL_DB_HOST"].strip(),
        dbname=os.environ["SQL_DB_NAME"].strip(),
        user=os.environ["SQL_DB_USER"].strip(),
        password=os.environ["SQL_DB_PASSWORD"],
        port=os.environ["SQL_DB_PORT"].strip(),
        connect_timeout=5,
    )


def _close_safely(cursor=None, connection=None):
    if cursor is not None:
        cursor.close()
    if connection is not None:
        connection.close()


def _normalize_json_value(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, type(default)):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return default
        return decoded if isinstance(decoded, type(default)) else default
    return default


def _telemetry_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    telemetry = metadata.get("telemetry") if isinstance(metadata, dict) else None
    return _normalize_json_value(telemetry, {})


def _grounding_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    grounding = metadata.get("grounding") if isinstance(metadata, dict) else None
    return _normalize_json_value(grounding, {})


def _safety_boundary_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    safety_boundary = metadata.get("safety_boundary") if isinstance(metadata, dict) else None
    return _normalize_json_value(safety_boundary, {})


def ensure_message_observability_schema() -> bool:
    """Backfill evaluation columns/tables on existing databases."""
    global _MESSAGE_OBSERVABILITY_SCHEMA_READY

    if _MESSAGE_OBSERVABILITY_SCHEMA_READY is not None:
        return _MESSAGE_OBSERVABILITY_SCHEMA_READY

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND table_name = 'messages'
                  AND column_name = 'metadata'
            );
            """
        )
        has_metadata_column = bool(cursor.fetchone()[0])
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                  AND table_name = 'message_evidence'
            );
            """
        )
        has_message_evidence_table = bool(cursor.fetchone()[0])
        if has_metadata_column and has_message_evidence_table:
            _MESSAGE_OBSERVABILITY_SCHEMA_READY = True
            return True

        cursor.execute(
            """
            ALTER TABLE messages
            ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
            """
        )
        cursor.execute(
            """
            ALTER TABLE messages
            ALTER COLUMN metadata SET DEFAULT '{}'::jsonb;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS message_evidence (
                evidence_id SERIAL PRIMARY KEY,
                message_id INTEGER NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
                evidence_type TEXT NOT NULL,
                evidence_payload JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        connection.commit()
        _MESSAGE_OBSERVABILITY_SCHEMA_READY = True
        return True
    except Exception as exc:
        if connection is not None:
            connection.rollback()
        print(
            "Message observability schema is not available; "
            f"continuing without message metadata/evidence persistence: {exc}"
        )
        _MESSAGE_OBSERVABILITY_SCHEMA_READY = False
        return False
    finally:
        _close_safely(cursor, connection)


def _insert_message_evidence_rows(cursor, message_id: int, evidence_rows: list[dict]):
    for evidence in evidence_rows:
        evidence_type = str(evidence.get("evidence_type") or "").strip()
        evidence_payload = _normalize_json_value(evidence.get("evidence_payload"), {})
        if not evidence_type or not evidence_payload:
            continue
        cursor.execute(
            """
            INSERT INTO message_evidence (message_id, evidence_type, evidence_payload)
            VALUES (%s, %s, %s);
            """,
            (message_id, evidence_type, Json(evidence_payload)),
        )


def ensure_rating_table_exists():
    """Create the ratings table if it has not been initialized yet."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ratings (
                rating_id SERIAL PRIMARY KEY,
                user_id INTEGER NULL REFERENCES users(user_id) ON DELETE SET NULL,
                rating DOUBLE PRECISION NOT NULL,
                message INTEGER NOT NULL UNIQUE REFERENCES messages(message_id) ON DELETE CASCADE,
                version TEXT NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            );
            """
        )
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def insert_user(username: str, email: str, password: str) -> int:
    """Insert a new user into the users table and return user_id."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash, created_at)
            VALUES (%s, %s, %s, NOW())
            RETURNING user_id;
            """,
            (username, email, password),
        )
        user_id = cursor.fetchone()[0]
        connection.commit()
        return user_id
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def insert_temporary_user(email: str) -> int:
    """Insert a new email-backed temporary user and return user_id."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO users (email, created_at, last_logged_in)
            VALUES (%s, NOW(), NOW())
            RETURNING user_id;
            """,
            (email,),
        )
        result = cursor.fetchone()
        connection.commit()
        if not result:
            raise RuntimeError("Failed to create temporary user.")
        return result[0]
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def insert_empty_user() -> int:
    """Legacy guard for the previous anonymous temporary-user flow."""
    raise ValueError("Temporary users must provide an email address.")


def get_users(filter: str = "all") -> list[User]:
    """Select users from the users table."""
    connection = None
    cursor = None
    try:
        if filter not in {"all", "regular", "temporary"}:
            raise ValueError("Invalid filter type. Use 'all', 'regular', or 'temporary'.")

        connection = get_connection()
        cursor = connection.cursor()

        if filter == "regular":
            query = """
                SELECT user_id, username, email, created_at, last_logged_in
                FROM users
                WHERE username IS NOT NULL
                    AND email IS NOT NULL
                    AND password_hash IS NOT NULL;
            """
        elif filter == "temporary":
            query = """
                SELECT user_id, username, email, created_at, last_logged_in
                FROM users
                WHERE username IS NULL OR password_hash IS NULL;
            """
        else:
            query = """
                SELECT user_id, username, email, created_at, last_logged_in
                FROM users;
            """

        cursor.execute(query)
        users = cursor.fetchall()

        return [
            {
                "user_id": user[0],
                "username": user[1],
                "email": user[2],
                "created_at": user[3],
                "last_logged_in": user[4],
            }
            for user in users
        ]
    finally:
        _close_safely(cursor, connection)


def get_selected_user(
    column_name: str, filter_value: str | int, include_password: bool = False
) -> User:
    """Select a single user filtered by a validated column name."""
    connection = None
    cursor = None
    try:
        if column_name not in ALLOWED_USER_COLUMNS:
            raise ValueError("Invalid column name.")

        if column_name == "user_id" and not isinstance(filter_value, int):
            raise TypeError("'filter_value' should be 'int' for user_id column name.")

        if column_name in {"username", "email"} and not isinstance(filter_value, str):
            raise TypeError("'filter_value' should be 'str' for username and email column name.")

        connection = get_connection()
        cursor = connection.cursor()
        if column_name == "email":
            query = """
                SELECT user_id, username, email, password_hash, created_at, last_logged_in
                FROM users
                WHERE LOWER(email) = LOWER(%s);
            """
        else:
            query = sql.SQL(
                """
                SELECT user_id, username, email, password_hash, created_at, last_logged_in
                FROM users
                WHERE {column} = %s;
                """
            ).format(column=sql.Identifier(column_name))

        cursor.execute(query, (filter_value,))
        user_row = cursor.fetchone()

        if not user_row:
            raise KeyError("User not found for given filters.")

        user_dict = {
            "user_id": user_row[0],
            "username": user_row[1],
            "email": user_row[2],
            "created_at": user_row[4],
            "last_logged_in": user_row[5],
        }

        if include_password:
            user_dict["password_hash"] = user_row[3]

        return user_dict
    finally:
        _close_safely(cursor, connection)


def update_user(user_id: int, username: str, email: str, password: str):
    """Update a temporary user into a regular user."""
    connection = None
    cursor = None
    try:
        selected_user = get_selected_user(
            column_name="user_id", filter_value=user_id, include_password=True
        )

        if selected_user["username"] is not None or selected_user.get("password_hash") is not None:
            raise ValueError("Cannot update a regular user to another regular user.")

        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE users
            SET username = %s,
                email = %s,
                password_hash = %s,
                last_logged_in = NOW()
            WHERE user_id = %s;
            """,
            (username, email, password, user_id),
        )
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def insert_session(user_id: int, session_token: str, is_active: bool) -> int:
    """Insert a new session and return session_id."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (user_id, session_token, is_active, created_at, last_accessed)
            VALUES (%s, %s, %s, NOW(), NOW())
            RETURNING session_id;
            """,
            (user_id, session_token, is_active),
        )
        session_id = cursor.fetchone()[0]
        connection.commit()
        return session_id
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def update_session(session_id: int, last_access_time: str, is_active: bool):
    """Update the session with the given session_id."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE sessions
            SET last_accessed = %s,
                is_active = %s
            WHERE session_id = %s;
            """,
            (last_access_time, is_active, session_id),
        )
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def get_selected_session(
    column_name: str, filter_value: int | str, filter_is_active: bool = False
) -> list[Session]:
    """Select sessions filtered by a validated column name."""
    connection = None
    cursor = None
    try:
        if column_name not in ALLOWED_SESSION_COLUMNS:
            raise ValueError("Invalid column name.")

        connection = get_connection()
        cursor = connection.cursor()

        if filter_is_active:
            query = sql.SQL(
                """
                SELECT session_id, user_id, session_token, is_active, created_at, last_accessed
                FROM sessions
                WHERE {column} = %s AND is_active = TRUE;
                """
            ).format(column=sql.Identifier(column_name))
            params = (filter_value,)
        else:
            query = sql.SQL(
                """
                SELECT session_id, user_id, session_token, is_active, created_at, last_accessed
                FROM sessions
                WHERE {column} = %s;
                """
            ).format(column=sql.Identifier(column_name))
            params = (filter_value,)

        cursor.execute(query, params)
        session_rows = cursor.fetchall()

        return [
            {
                "session_id": session[0],
                "user_id": session[1],
                "session_token": session[2],
                "is_active": session[3],
                "created_at": session[4],
                "last_accessed": session[5],
            }
            for session in session_rows
        ]
    finally:
        _close_safely(cursor, connection)


def get_all_sessions() -> list[Session]:
    """Select all rows from the sessions table."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT session_id, user_id, session_token, is_active, last_accessed
            FROM sessions;
            """
        )
        sessions = cursor.fetchall()

        return [
            {
                "session_id": session[0],
                "user_id": session[1],
                "session_token": session[2],
                "is_active": session[3],
                "last_accessed": session[4],
            }
            for session in sessions
        ]
    finally:
        _close_safely(cursor, connection)


def get_selected_messages(column_name: str, filter_value: int) -> list[Message]:
    """Select messages filtered by a validated column name."""
    connection = None
    cursor = None
    try:
        if column_name not in ALLOWED_MESSAGE_COLUMNS:
            raise ValueError("Invalid column name.")

        observability_ready = ensure_message_observability_schema()
        connection = get_connection()
        cursor = connection.cursor()
        metadata_select = (
            sql.SQL("m.metadata")
            if observability_ready
            else sql.SQL("'{}'::jsonb AS metadata")
        )
        query = sql.SQL(
            """
            SELECT
                m.message_id,
                m.session_id,
                m.role,
                m.content,
                m.sent_at,
                CASE WHEN m.role = 'assistant' THEN r.rating_id ELSE NULL END AS rating_id,
                CASE WHEN m.role = 'assistant' THEN r.rating ELSE NULL END AS rating,
                CASE WHEN m.role = 'assistant' THEN r.version ELSE NULL END AS version,
                {metadata_select}
            FROM messages AS m
            LEFT JOIN ratings AS r
                ON r.message = m.message_id
            WHERE m.{column} = %s
            ORDER BY m.sent_at ASC, m.message_id ASC;
            """
        ).format(
            metadata_select=metadata_select,
            column=sql.Identifier(column_name),
        )
        cursor.execute(query, (filter_value,))
        message_rows = cursor.fetchall()

        return [
            {
                "message_id": message[0],
                "session_id": message[1],
                "role": message[2],
                "content": message[3],
                "sent_at": message[4],
                "rating_id": message[5],
                "rating": message[6],
                "version": message[7],
                "metadata": _normalize_json_value(message[8], {}),
            }
            for message in message_rows
        ]
    finally:
        _close_safely(cursor, connection)

def ensure_advisor_review_table_exists():
    """Create the advisor review table for structured evaluation rubrics."""
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS advisor_reviews (
                advisor_review_id SERIAL PRIMARY KEY,
                message_id INTEGER NOT NULL UNIQUE REFERENCES messages(message_id) ON DELETE CASCADE,
                reviewer_user_id INTEGER NULL REFERENCES users(user_id) ON DELETE SET NULL,
                route_correct BOOLEAN NULL,
                building_data_correct BOOLEAN NULL,
                recommendation_correct BOOLEAN NULL,
                personalized BOOLEAN NULL,
                useful BOOLEAN NULL,
                too_generic BOOLEAN NULL,
                needs_minor_edit BOOLEAN NULL,
                needs_major_edit BOOLEAN NULL,
                unsafe_or_misleading BOOLEAN NULL,
                should_have_asked_clarification BOOLEAN NULL,
                should_have_escalated BOOLEAN NULL,
                technical_correctness_score DOUBLE PRECISION NULL,
                building_specificity_score DOUBLE PRECISION NULL,
                personalization_score DOUBLE PRECISION NULL,
                usefulness_score DOUBLE PRECISION NULL,
                justification_score DOUBLE PRECISION NULL,
                clarity_score DOUBLE PRECISION NULL,
                trust_score DOUBLE PRECISION NULL,
                safety_score DOUBLE PRECISION NULL,
                advisor_confidence DOUBLE PRECISION NULL,
                error_tags JSONB NOT NULL DEFAULT '[]'::jsonb,
                correction_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
                corrected_answer TEXT NULL,
                correction_summary TEXT NULL,
                comments TEXT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            );
            """
        )
        cursor.execute(
            """
            ALTER TABLE advisor_reviews
            ADD COLUMN IF NOT EXISTS correction_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS corrected_answer TEXT NULL,
            ADD COLUMN IF NOT EXISTS correction_summary TEXT NULL;
            """
        )
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def upsert_advisor_review(
    *,
    message_id: int,
    reviewer_user_id: int,
    review: dict[str, Any],
) -> dict[str, Any]:
    """Insert or update one advisor rubric review for an assistant message."""
    connection = None
    cursor = None
    try:
        ensure_advisor_review_table_exists()
        connection = get_connection()
        cursor = connection.cursor()

        field_names = [
            *ADVISOR_REVIEW_BOOLEAN_FIELDS,
            *ADVISOR_REVIEW_SCORE_FIELDS,
            "error_tags",
            *ADVISOR_REVIEW_CORRECTION_FIELDS,
            "comments",
        ]
        values = []
        for field_name in field_names:
            if field_name in {"error_tags", "correction_actions"}:
                values.append(Json(_normalize_json_value(review.get(field_name), [])))
            else:
                values.append(review.get(field_name))

        insert_columns = ["message_id", "reviewer_user_id", *field_names]
        placeholders = ", ".join(["%s"] * len(insert_columns))
        update_assignments = ", ".join(
            f"{field_name} = EXCLUDED.{field_name}"
            for field_name in ["reviewer_user_id", *field_names]
        )

        cursor.execute(
            f"""
            INSERT INTO advisor_reviews ({", ".join(insert_columns)})
            VALUES ({placeholders})
            ON CONFLICT (message_id) DO UPDATE
            SET {update_assignments},
                updated_at = NOW()
            RETURNING advisor_review_id, message_id, reviewer_user_id, updated_at;
            """,
            [message_id, reviewer_user_id, *values],
        )
        row = cursor.fetchone()
        connection.commit()
        return {
            "advisor_review_id": row[0],
            "message_id": row[1],
            "reviewer_user_id": row[2],
            "updated_at": row[3],
        }
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def get_evaluation_records(
    *,
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Return one export row per assistant answer for evaluation analysis."""
    connection = None
    cursor = None
    try:
        ensure_message_observability_schema()
        ensure_rating_table_exists()
        ensure_advisor_review_table_exists()
        connection = get_connection()
        cursor = connection.cursor()

        filters = []
        params: list[Any] = []
        if user_id is not None:
            filters.append("s.user_id = %s")
            params.append(user_id)
        if session_id is not None:
            filters.append("s.session_id = %s")
            params.append(session_id)

        where_clause = ""
        if filters:
            where_clause = "WHERE " + " AND ".join(filters)

        query = f"""
            WITH ordered_messages AS (
                SELECT
                    m.message_id,
                    m.session_id,
                    m.role,
                    m.content,
                    m.sent_at,
                    m.metadata,
                    LAG(m.message_id) OVER (
                        PARTITION BY m.session_id
                        ORDER BY m.sent_at ASC, m.message_id ASC
                    ) AS previous_message_id,
                    LAG(m.role) OVER (
                        PARTITION BY m.session_id
                        ORDER BY m.sent_at ASC, m.message_id ASC
                    ) AS previous_role,
                    LAG(m.content) OVER (
                        PARTITION BY m.session_id
                        ORDER BY m.sent_at ASC, m.message_id ASC
                    ) AS previous_content,
                    LAG(m.sent_at) OVER (
                        PARTITION BY m.session_id
                        ORDER BY m.sent_at ASC, m.message_id ASC
                    ) AS previous_sent_at
                FROM messages AS m
                JOIN sessions AS s
                    ON s.session_id = m.session_id
                {where_clause}
            )
            SELECT
                om.session_id,
                s.session_token,
                s.user_id,
                u.username,
                CASE WHEN om.previous_role = 'user' THEN om.previous_message_id ELSE NULL END AS query_message_id,
                om.message_id AS answer_message_id,
                CASE WHEN om.previous_role = 'user' THEN om.previous_sent_at ELSE NULL END AS query_sent_at,
                om.sent_at AS answer_sent_at,
                CASE WHEN om.previous_role = 'user' THEN om.previous_content ELSE NULL END AS user_message,
                om.content AS assistant_content,
                r.rating,
                r.rating_id,
                r.version AS rating_version,
                om.metadata,
                ar.advisor_review,
                COALESCE(
                    jsonb_agg(
                        jsonb_build_object(
                            'evidence_type', me.evidence_type,
                            'evidence_payload', me.evidence_payload
                        )
                        ORDER BY me.evidence_id
                    ) FILTER (WHERE me.evidence_id IS NOT NULL),
                    '[]'::jsonb
                ) AS evidence
            FROM ordered_messages AS om
            JOIN sessions AS s
                ON s.session_id = om.session_id
            LEFT JOIN users AS u
                ON u.user_id = s.user_id
            LEFT JOIN ratings AS r
                ON r.message = om.message_id
            LEFT JOIN message_evidence AS me
                ON me.message_id = om.message_id
            LEFT JOIN LATERAL (
                SELECT jsonb_build_object(
                    'advisor_review_id', advisor_review_id,
                    'reviewer_user_id', reviewer_user_id,
                    'route_correct', route_correct,
                    'building_data_correct', building_data_correct,
                    'recommendation_correct', recommendation_correct,
                    'personalized', personalized,
                    'useful', useful,
                    'too_generic', too_generic,
                    'needs_minor_edit', needs_minor_edit,
                    'needs_major_edit', needs_major_edit,
                    'unsafe_or_misleading', unsafe_or_misleading,
                    'should_have_asked_clarification', should_have_asked_clarification,
                    'should_have_escalated', should_have_escalated,
                    'technical_correctness_score', technical_correctness_score,
                    'building_specificity_score', building_specificity_score,
                    'personalization_score', personalization_score,
                    'usefulness_score', usefulness_score,
                    'justification_score', justification_score,
                    'clarity_score', clarity_score,
                    'trust_score', trust_score,
                    'safety_score', safety_score,
                    'advisor_confidence', advisor_confidence,
                    'error_tags', error_tags,
                    'correction_actions', correction_actions,
                    'corrected_answer', corrected_answer,
                    'correction_summary', correction_summary,
                    'comments', comments,
                    'updated_at', updated_at
                ) AS advisor_review
                FROM advisor_reviews
                WHERE advisor_reviews.message_id = om.message_id
            ) AS ar ON TRUE
            WHERE om.role = 'assistant'
            GROUP BY
                om.session_id,
                s.session_token,
                s.user_id,
                u.username,
                om.previous_role,
                om.previous_message_id,
                om.previous_sent_at,
                om.message_id,
                om.sent_at,
                om.previous_content,
                om.content,
                r.rating,
                r.rating_id,
                r.version,
                om.metadata,
                ar.advisor_review
            ORDER BY om.sent_at ASC, om.message_id ASC;
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()
        records = []
        for row in rows:
            metadata = _normalize_json_value(row[13], {})
            telemetry = _telemetry_from_metadata(metadata)
            grounding = _grounding_from_metadata(metadata)
            safety_boundary = _safety_boundary_from_metadata(metadata)
            advisor_review = _normalize_json_value(row[14], {})
            evidence = _normalize_json_value(row[15], [])
            building_match = metadata.get("building_match") or {}
            retrieved_facts = metadata.get("retrieved_facts") or {}
            byggnadsid = (
                metadata.get("byggnadsid")
                or metadata.get("selected_brf_building_id")
                or metadata.get("building_id_from_user")
                or retrieved_facts.get("byggnadsid")
                or retrieved_facts.get("building_id")
            )
            building_id = (
                metadata.get("building_id")
                or byggnadsid
                or building_match.get("building_id")
            )
            address_used = (
                metadata.get("requested_address")
                or metadata.get("address")
                or metadata.get("address_from_user")
                or building_match.get("input_address")
                or retrieved_facts.get("address")
                or retrieved_facts.get("epc_idadr")
            )
            session_join_key = f"spara-session-{row[0]}"
            message_join_key = f"{session_join_key}-answer-{row[5]}"
            record = {
                "session_join_key": session_join_key,
                "message_join_key": message_join_key,
                "session_id": row[0],
                "session_token": row[1],
                "thread_id": row[1],
                "user_id": row[2],
                "username": row[3],
                "query_message_id": row[4],
                "answer_message_id": row[5],
                "query_sent_at": row[6],
                "answer_sent_at": row[7],
                "user_message": row[8],
                "assistant_content": row[9],
                "rating": row[10],
                "rating_id": row[11],
                "rating_version": row[12],
                "route": metadata.get("route"),
                "agent": metadata.get("agent"),
                "classification": metadata.get("classification"),
                "intent": metadata.get("intent"),
                "needs_clarification": metadata.get("needs_clarification"),
                "out_of_scope": metadata.get("out_of_scope"),
                "building_id": building_id,
                "byggnadsid": byggnadsid,
                "address_used": address_used,
                "requested_address": metadata.get("requested_address"),
                "address_from_user": metadata.get("address_from_user"),
                "epc_record_address": metadata.get("epc_record_address"),
                "same_building_multiple_addresses": metadata.get("same_building_multiple_addresses"),
                "building_match": building_match,
                "retrieved_facts": retrieved_facts,
                "vector_sources": metadata.get("vector_sources") or [],
                "grounding": grounding,
                "grounding_status": grounding.get("status"),
                "claim_count": grounding.get("claim_count"),
                "supported_claim_count": grounding.get("supported_claim_count"),
                "unsupported_claim_count": grounding.get("unsupported_claim_count"),
                "support_ratio": grounding.get("support_ratio"),
                "unsupported_claim_rate": grounding.get("unsupported_claim_rate"),
                "citation_coverage": grounding.get("citation_coverage"),
                "unsupported_claims": grounding.get("unsupported_claims") or [],
                "data_freshness": metadata.get("data_freshness") or {},
                "uncertainty": metadata.get("uncertainty") or {},
                "boundary_handling": metadata.get("boundary_handling") or {},
                "safety_boundary": safety_boundary,
                "safety_status": safety_boundary.get("status"),
                "safety_risk_category": safety_boundary.get("risk_category"),
                "safety_action": safety_boundary.get("action"),
                "safety_handled_safely": safety_boundary.get("handled_safely"),
                "safety_requires_review": safety_boundary.get("requires_review"),
                "safety_redirect_to": safety_boundary.get("redirect_to"),
                "safety_reason_codes": safety_boundary.get("reason_codes") or [],
                "telemetry": telemetry,
                "total_latency_seconds": telemetry.get("total_latency_seconds"),
                "model_call_count": telemetry.get("model_call_count"),
                "retrieval_call_count": telemetry.get("retrieval_call_count"),
                "sql_call_count": telemetry.get("sql_call_count"),
                "prompt_tokens": telemetry.get("prompt_tokens"),
                "completion_tokens": telemetry.get("completion_tokens"),
                "total_tokens": telemetry.get("total_tokens"),
                "token_usage_estimated": telemetry.get("token_usage_estimated"),
                "estimated_cost_usd": telemetry.get("estimated_cost_usd"),
                "component_latency_seconds": telemetry.get("component_latency_seconds") or {},
                "telemetry_failures": telemetry.get("failures") or [],
                "metadata": metadata,
                "advisor_review": advisor_review,
                "evidence": evidence,
            }
            if advisor_review:
                record["advisor_review_id"] = advisor_review.get("advisor_review_id")
                record["advisor_reviewer_user_id"] = advisor_review.get("reviewer_user_id")
                for review_field in (
                    *ADVISOR_REVIEW_BOOLEAN_FIELDS,
                    *ADVISOR_REVIEW_SCORE_FIELDS,
                    "error_tags",
                    *ADVISOR_REVIEW_CORRECTION_FIELDS,
                    "comments",
                ):
                    record[review_field] = advisor_review.get(review_field)
            records.append(record)
        return records
    finally:
        _close_safely(cursor, connection)


def insert_messages(messages: list[dict]):
    """Insert multiple messages into the messages table."""
    connection = None
    cursor = None
    if not messages:
        raise ValueError("Messages list is empty.")

    invalid_roles = [m["role"] for m in messages if m["role"] not in VALID_MESSAGE_ROLES]
    if invalid_roles:
        raise ValueError(
            "Invalid role type in messages list. Valid roles are 'user', 'assistant', 'system'."
        )

    inserted_message_ids = []
    try:
        observability_ready = ensure_message_observability_schema()
        connection = get_connection()
        cursor = connection.cursor()
        if observability_ready:
            insert_query = """
                INSERT INTO messages (session_id, role, content, sent_at, metadata)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING message_id;
            """
        else:
            insert_query = """
                INSERT INTO messages (session_id, role, content, sent_at)
                VALUES (%s, %s, %s, %s)
                RETURNING message_id;
            """
        for msg in messages:
            metadata = _normalize_json_value(msg.get("metadata"), {})
            params = (
                    msg["session_id"],
                    msg["role"],
                    msg["content"],
                    msg["sent_at"],
            )
            if observability_ready:
                params = (*params, Json(metadata))
            cursor.execute(insert_query, params)
            inserted_message_id = cursor.fetchone()[0]
            inserted_message_ids.append(inserted_message_id)
            evidence_rows = _normalize_json_value(msg.get("evidence"), [])
            if observability_ready and evidence_rows:
                _insert_message_evidence_rows(cursor, inserted_message_id, evidence_rows)
        connection.commit()
        return inserted_message_ids
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def insert_rating(user_id, rating, message, version):
    connection = None
    cursor = None
    user_id_value: Any = None if user_id == 1 else user_id

    try:
        ensure_rating_table_exists()
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO ratings (user_id, rating, message, version)
            VALUES (%s, %s, %s, %s)
            RETURNING rating_id;
            """,
            (user_id_value, rating, message, version),
        )
        rating_id = cursor.fetchone()[0]
        connection.commit()
        return rating_id
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)


def check_rating_exists(message_id):
    connection = None
    cursor = None
    try:
        ensure_rating_table_exists()
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT rating_id
            FROM ratings
            WHERE message = %s;
            """,
            (message_id,),
        )
        result = cursor.fetchone()
        return result[0] if result is not None else None
    finally:
        _close_safely(cursor, connection)


def update_rating(rating_id, rating):
    connection = None
    cursor = None
    try:
        ensure_rating_table_exists()
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE ratings
            SET rating = %s
            WHERE rating_id = %s;
            """,
            (rating, rating_id),
        )
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        _close_safely(cursor, connection)
