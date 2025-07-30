from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
import psycopg2.errors
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address

from service.authorization import AuthorizationService
from service.database import (
    get_users,
    get_selected_user,
    insert_user,
    insert_empty_user,
    get_selected_session,
    insert_session,
    get_selected_messages,
    insert_messages,
    Message,
    insert_rating,
    check_rating_exists,
    update_rating,
)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class RegisterBody(BaseModel):
    username: str
    email: EmailStr
    password: str


class MessageBody(BaseModel):
    session_id: int
    role: str
    content: str
    sent_at: str


class RatingBody(BaseModel):
    userId: int
    rating: float
    message: str
    sessionIdInt: int


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
        user = get_selected_user(
            column_name="email", filter_value=form_data.username, include_password=True
        )
        print(f"User found: {user}")

    except KeyError:
        # no such user
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
        )

    # Verify the provided password against the stored hash
    if not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
        )

    # Create a signed JWT token
    token = auth_service.create_token(
        user_id=user["user_id"], email=user["email"], temporary_user=False
    )

    return {"access_token": token, "token_type": "bearer", "user_id": user["user_id"]}


@router.post("/user/login/temporary/", tags=["users"])
@limiter.limit("10/minute")
async def login_temporary_user(temp_user_id: int):
    """Login endpoint for temporary users.
    This endpoint creates a signed JWT token for a temporary user.
    Args:
        temp_user_id (int): The ID of the temporary user.
    Returns:
        dict: A dictionary containing the access token, token type, user ID, and a flag indicating it's a temporary user.
    """
    # Create a signed JWT token
    token = auth_service.create_token(
        user_id=temp_user_id, email="", temporary_user=True
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": temp_user_id,
        "temporary_user": True,
    }


@router.post("/user/register/", tags=["users"])
@limiter.limit("10/minute")
async def register(request: Request, body: RegisterBody):
    users = get_users(filter="regular")

    # Check for existing email
    if any(u["email"].lower() == body.email.lower() for u in users if u["email"]):
        raise HTTPException(status_code=400, detail="Email already registered.")

    # Hash the password
    hashed_pw = get_password_hash(body.password)

    # Insert new user
    try:
        new_user_id = insert_user(
            username=body.username, email=body.email, password=hashed_pw
        )
    except Exception as e:
        raise e

    # Return the new user's ID
    return {"user_id": new_user_id, "message": "User registered successfully."}


@router.post("/user/register/temporary/", tags=["users"])
@limiter.limit("10/minute")
async def register_temporary_user():
    try:
        result = insert_empty_user()
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
        result = insert_session(
            user_id=user_id, session_token=session_token, is_active=is_active
        )
        return result
    except psycopg2.errors.ForeignKeyViolation as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


# MESSAGE Entrypoints


@router.get("/messages/{session_id}/", tags=["messages"])
async def get_messages_by_session_id(
    session_id: int, auth: dict = Depends(auth_service.get_token_data)
):
    try:
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
        messages_dict = [m.__dict__ for m in messages]
        result = insert_messages(messages=messages_dict)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except psycopg2.errors.ForeignKeyViolation as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


@router.post("/rating/")
async def send_rating(ratingbody: RatingBody):
    # version=os.getenv("VERSION_NUMBER", "0.5.0")
    messages = await get_messages_by_session_id(ratingbody.sessionIdInt)
    # Filter out the message with the same content as ratingbody.message
    target_message = next(
        (m for m in messages if m["content"] == ratingbody.message), None
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


# Helpers


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
