import base64
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
import psycopg2.errors
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from service.authorization import AuthorizationService
from service.database import (
    get_users,
    get_selected_user,
    insert_user,
    insert_temporary_user,
    update_user,
    get_selected_session,
    insert_session,
    get_selected_messages,
    get_evaluation_records,
    upsert_advisor_review,
    insert_messages,
    update_session,
    Message,
    insert_rating,
    check_rating_exists,
    update_rating,
)
from service.evaluation_export import (
    evaluation_records_to_csv,
    evaluation_records_to_jsonl,
)
from service.report_store import get_report_payload


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class TemporaryUserLoginBody(BaseModel):
    temp_user_id: int


class TemporaryUserRegisterBody(BaseModel):
    email: EmailStr


class RegisterBody(BaseModel):
    username: str
    email: EmailStr
    password: str


class MessageBody(BaseModel):
    session_id: int
    role: str
    content: str
    sent_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class RatingBody(BaseModel):
    userId: int
    rating: float
    message: str | None = None
    sessionIdInt: int
    messageId: int | None = None


class AdvisorReviewBody(BaseModel):
    message_id: int
    route_correct: bool | None = None
    building_data_correct: bool | None = None
    recommendation_correct: bool | None = None
    personalized: bool | None = None
    useful: bool | None = None
    too_generic: bool | None = None
    needs_minor_edit: bool | None = None
    needs_major_edit: bool | None = None
    unsafe_or_misleading: bool | None = None
    should_have_asked_clarification: bool | None = None
    should_have_escalated: bool | None = None
    technical_correctness_score: float | None = None
    building_specificity_score: float | None = None
    personalization_score: float | None = None
    usefulness_score: float | None = None
    justification_score: float | None = None
    clarity_score: float | None = None
    trust_score: float | None = None
    safety_score: float | None = None
    advisor_confidence: float | None = None
    error_tags: list[str] = Field(default_factory=list)
    correction_actions: list[dict[str, Any]] = Field(default_factory=list)
    corrected_answer: str | None = None
    correction_summary: str | None = None
    comments: str | None = None


# Create a router instance
router = APIRouter()
auth_service = AuthorizationService()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# USER entrypoints


@router.get("/users/", tags=["users"])
async def get_all_users(auth: dict = Depends(auth_service.get_token_data)):
    try:
        # TODO: Only allow admin users to access this endpoint. After implementing roles.
        if auth.get("temporary_user"):
            raise HTTPException(
                status_code=403,
                detail="Temporary users cannot access this resource",
            )

        result = get_users()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


@router.get("/user/{user_id}/", tags=["users"])
async def get_user_by_user_id(
    user_id: int, auth: dict = Depends(auth_service.get_token_data)
):
    try:
        _ensure_user(user_id, auth)
        result = get_selected_user(column_name="user_id", filter_value=user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


@router.post("/user/login/", tags=["users"])
@limiter.limit("10/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # Fetch user by email
    try:
        email = _normalize_email(form_data.username)
        user = get_selected_user(
            column_name="email", filter_value=email, include_password=True
        )
        print(f"User found: {user}")

    except KeyError:
        # no such user
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
        )

    if not user.get("password_hash"):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
        )

    # Verify the provided password against the stored hash
    if not _verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
        )

    # Create a signed JWT token
    token = auth_service.create_token(
        user_id=user["user_id"], email=user["email"], temporary_user=False
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user["email"],
        "temporary_user": False,
    }


@router.post("/user/login/temporary/", tags=["users"])
@limiter.limit("10/minute")
async def login_temporary_user(request: Request, data: TemporaryUserLoginBody):
    """Login endpoint for temporary users.
    This endpoint creates a signed JWT token for a temporary user.
    Args:
        temp_user_id (int): The ID of the temporary user.
    Returns:
        dict: A dictionary containing the access token, token type, user ID, and a flag indicating it's a temporary user.
    Raises:
        HTTPException: If the user is not a temporary user or doesn't exist.
    """

    try:
        # Fetch user by user_id to validate it exists and check if it's temporary
        temp_user_id = data.temp_user_id
        user = get_selected_user(
            column_name="user_id", filter_value=temp_user_id, include_password=True
        )

        # Check if this is actually a temporary user
        # Temporary users have an email, but no username/password credentials yet.
        if user.get("username") or user.get("password_hash"):
            raise HTTPException(
                status_code=403,
                detail="Cannot login as temporary user: This is a regular user account with credentials.",
            )

        if not user.get("email"):
            raise HTTPException(
                status_code=400,
                detail="Temporary users must have an email address.",
            )

    except KeyError:
        # User doesn't exist
        raise HTTPException(
            status_code=404,
            detail="Temporary user not found.",
        )

    # Create a signed JWT token for the temporary user
    token = auth_service.create_token(
        user_id=temp_user_id, email=user["email"], temporary_user=True
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": temp_user_id,
        "email": user["email"],
        "username": user.get("username"),
        "temporary_user": True,
    }


@router.post("/user/register/", tags=["users"])
@limiter.limit("10/minute")
async def register(request: Request, body: RegisterBody):
    try:
        users = get_users(filter="regular")
        email = _normalize_email(body.email)

        # Check for existing email
        if any(_normalize_email(u["email"]) == email for u in users if u["email"]):
            raise HTTPException(status_code=400, detail="Email already registered.")

        # Hash the password
        hashed_pw = _get_password_hash(body.password)

        # Insert new user
        new_user_id = insert_user(
            username=body.username, email=email, password=hashed_pw
        )
    except Exception as e:
        raise e

    # Return the new user's ID
    return {"user_id": new_user_id, "message": "User registered successfully."}


@router.post("/user/register/temporary/", tags=["users"])
@limiter.limit("10/minute")
async def register_temporary_user(request: Request, body: TemporaryUserRegisterBody):
    try:
        email = _normalize_email(body.email)
        try:
            existing_user = get_selected_user(
                column_name="email", filter_value=email, include_password=True
            )
        except KeyError:
            existing_user = None

        if existing_user:
            if existing_user.get("username") or existing_user.get("password_hash"):
                raise HTTPException(
                    status_code=400,
                    detail="Email already registered. Please log in instead.",
                )

            return {
                "user_id": existing_user["user_id"],
                "email": _normalize_email(existing_user["email"]),
                "message": "Temporary user loaded successfully.",
            }

        user_id = insert_temporary_user(email=email)
        return {
            "user_id": user_id,
            "email": email,
            "message": "Temporary user created successfully.",
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise e


@router.post("/user/register/temporary-to-regular/{user_id}/", tags=["users"])
@limiter.limit("10/minute")
async def register_temporary_user_to_regular(user_id: int, request: Request, body: RegisterBody):
    try:
        users = get_users(filter="regular")
        email = _normalize_email(body.email)

        # Check for existing email
        if any(
            u["user_id"] != user_id and _normalize_email(u["email"]) == email
            for u in users
            if u["email"]
        ):
            raise HTTPException(status_code=400, detail="Email already registered.")

        # Hash the password
        hashed_pw = _get_password_hash(body.password)

        update_user(
            user_id=user_id,
            username=body.username,
            email=email,
            password=hashed_pw,
        )

        result = {"user_id": user_id, "message": "User updated successfully."}
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise e


# SESSION Entrypoints


@router.get("/session/{user_id}/", tags=["sessions"])
async def get_session_by_user_id(
    user_id: int,
    filter_active_sessions: bool = False,
    auth: dict = Depends(auth_service.get_token_data),
):
    try:
        _ensure_user(user_id, auth)

        result = get_selected_session(
            column_name="user_id",
            filter_value=user_id,
            filter_is_active=filter_active_sessions,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


@router.post("/session/", tags=["sessions"])
async def create_session(
    user_id: int,
    session_token: str,
    is_active: bool,
    auth: dict = Depends(auth_service.get_token_data),
):
    try:
        _ensure_user(user_id, auth)

        result = insert_session(
            user_id=user_id, session_token=session_token, is_active=is_active
        )
        return result
    except psycopg2.errors.ForeignKeyViolation as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


@router.patch("/session/{session_id}/active/", tags=["sessions"])
async def update_session_active_state(
    session_id: int,
    is_active: bool,
    auth: dict = Depends(auth_service.get_token_data),
):
    try:
        session = get_selected_session(
            column_name="session_id",
            filter_value=session_id,
        )
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found.",
            )

        session_owner_id = session[0]["user_id"]
        _ensure_user(session_owner_id, auth)

        timestamp = datetime.now(timezone.utc).isoformat()
        update_session(
            session_id=session_id,
            last_access_time=timestamp,
            is_active=is_active,
        )

        return {
            **session[0],
            "is_active": is_active,
            "last_accessed": timestamp,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


# MESSAGE Entrypoints


@router.get("/messages/{session_id}/", tags=["messages"])
async def get_messages_by_session_id(
    session_id: int, auth: dict = Depends(auth_service.get_token_data)
):
    try:
        session = get_selected_session(
            column_name="session_id", filter_value=session_id
        )
        if not session:
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found."
            )
        user_id = session[0]["user_id"]
        _ensure_user(user_id, auth)

        result = get_selected_messages(
            column_name="session_id", filter_value=session_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


@router.post("/messages/", tags=["messages"])
async def create_message(
    messages: list[MessageBody], auth: dict = Depends(auth_service.get_token_data)
):
    try:
        for m in messages:
            session = get_selected_session(
                column_name="session_id", filter_value=m.session_id
            )
            if not session:
                raise HTTPException(
                    status_code=404, detail=f"Session {m.session_id} not found."
                )
            user_id = session[0]["user_id"]
            _ensure_user(user_id, auth)

        messages_dict = [m.__dict__ for m in messages]
        result = insert_messages(messages=messages_dict)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except psycopg2.errors.ForeignKeyViolation as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


@router.post("/rating/", tags=["ratings"])
async def send_rating(
    ratingbody: RatingBody, auth: dict = Depends(auth_service.get_token_data)
):
    _ensure_user(ratingbody.userId, auth)

    # version=os.getenv("VERSION_NUMBER", "0.5.0")
    messages = await get_messages_by_session_id(ratingbody.sessionIdInt, auth)

    if ratingbody.messageId is not None:
        target_message = next(
            (
                m
                for m in messages
                if m.get("message_id") == ratingbody.messageId
                and m.get("role") == "assistant"
            ),
            None,
        )
    else:
        target_message = next(
            (
                m
                for m in reversed(messages)
                if m.get("content") == ratingbody.message
                and m.get("role") == "assistant"
            ),
            None,
        )
    if not target_message:
        raise HTTPException(status_code=404, detail="Message not found for rating.")
    message_id = target_message["message_id"]
    rating_id = check_rating_exists(message_id)
    if ratingbody.sessionIdInt % 2 == 0:
        version = "GROUP-A"
    else:
        version = "GROUP-B"
    try:
        if rating_id:
            print(
                f"Rating already exists for message_id {message_id}, updating existing rating."
            )
            # Update the existing rating
            update_rating(rating_id, ratingbody.rating)
            return {"rating_id": rating_id, "message_id": message_id}
        else:
            rating_id = insert_rating(
                ratingbody.userId, ratingbody.rating, message_id, version
            )
            print(
                f"Rating with ID {rating_id} inserted into database for message_id {message_id}"
            )
            return {"rating_id": rating_id, "message_id": message_id}
    except Exception as e:
        raise e


@router.get("/reports/{report_id}/download/", tags=["reports"])
async def download_report(
    report_id: str, auth: dict = Depends(auth_service.get_token_data)
):
    payload = get_report_payload(report_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Report not found or expired.")

    thread_id = payload.get("thread_id")
    if not thread_id:
        raise HTTPException(status_code=404, detail="Report metadata is incomplete.")

    sessions = get_selected_session(column_name="session_token", filter_value=thread_id)
    if not sessions:
        raise HTTPException(status_code=404, detail="Owning session was not found.")

    session = sessions[0]
    _ensure_user(session["user_id"], auth)

    file_name = payload.get("file_name") or f"{report_id}.md"
    mime_type = payload.get("mime_type") or "text/plain"
    content_encoding = payload.get("content_encoding")

    if content_encoding == "base64":
        raw_content = payload.get("content_base64") or ""
        content = base64.b64decode(raw_content)
    else:
        content = payload.get("content") or ""

    return Response(
        content=content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/evaluation/export/", tags=["evaluation"])
async def export_evaluation_records(
    format: str = "jsonl",
    user_id: int | None = None,
    session_id: int | None = None,
    auth: dict = Depends(auth_service.get_token_data),
):
    if auth.get("temporary_user"):
        raise HTTPException(
            status_code=403,
            detail="Temporary users cannot export evaluation records.",
        )

    export_format = format.strip().lower()
    records = get_evaluation_records(user_id=user_id, session_id=session_id)

    if export_format == "jsonl":
        content = evaluation_records_to_jsonl(records)
        media_type = "application/x-ndjson; charset=utf-8"
        file_name = "spara-evaluation-records.jsonl"
    elif export_format == "csv":
        content = evaluation_records_to_csv(records)
        media_type = "text/csv; charset=utf-8"
        file_name = "spara-evaluation-records.csv"
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported export format. Use 'jsonl' or 'csv'.",
        )

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/evaluation/advisor-review/", tags=["evaluation"])
async def save_advisor_review(
    review: AdvisorReviewBody,
    auth: dict = Depends(auth_service.get_token_data),
):
    if auth.get("temporary_user"):
        raise HTTPException(
            status_code=403,
            detail="Temporary users cannot submit advisor reviews.",
        )

    try:
        return upsert_advisor_review(
            message_id=review.message_id,
            reviewer_user_id=auth["user_id"],
            review=review.__dict__,
        )
    except psycopg2.errors.ForeignKeyViolation as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


# Helpers


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _get_password_hash(password: str) -> str:
    """Hash a password for storing."""
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain, hashed)


def _ensure_user(resource_owner_id: int, auth_user: dict):
    """Ensure that the authenticated user is the resource owner else raise HTTP 403 Forbidden error."""
    if auth_user["user_id"] != resource_owner_id:
        raise HTTPException(status_code=403, detail="Forbidden")
