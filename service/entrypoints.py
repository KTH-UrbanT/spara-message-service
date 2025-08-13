# routes/api.py
import sys
import os
from fastapi import APIRouter, HTTPException
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
from pydantic import BaseModel, EmailStr
import psycopg2.errors

##from spara_backend.redis_pub_sub import RedisEventManager

# event_manager = RedisEventManager()


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

# USER entrypoints


@router.get("/users/")
async def get_all_users():
    try:
        result = get_users()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


@router.get("/user/{user_id}/")
async def get_user_by_user_id(user_id: int):
    try:
        result = get_selected_user(column_name="user_id", filter_value=user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e


@router.post("/user/register/")
async def register(body: RegisterBody):
    try:
        result = insert_user(
            username=body.username, email=body.email, password=body.password
        )
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise e


@router.post("/user/register/temporary/")
async def register_temporary_user():
    try:
        result = insert_empty_user()
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise e


@router.post("/user/login/")
async def login(body: LoginBody):
    try:
        # Get the user data by email
        user = get_selected_user(column_name="email", filter_value=body.email)

        # Validate the password
        if user["password"] != body.password:
            raise HTTPException(status_code=401, detail="Incorrect password.")

        # Return success response
        return {"message": "Login successful!", "user_id": user["user_id"]}

    except HTTPException as e:
        raise e  # Reraise HTTP exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error.")


# SESSION Entrypoints


@router.get("/session/{user_id}/")
async def get_session_by_user_id(user_id: int, filter_active_sessions: bool = False):
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


@router.post("/session/")
async def create_session(user_id: int, session_token: str, is_active: bool):
    try:
        result = insert_session(
            user_id=user_id, session_token=session_token, is_active=is_active
        )
        return result
    except psycopg2.errors.ForeignKeyViolation as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise e
    
    
@router.get("/messages/{session_id}/")
async def get_messages_by_session_id(session_id: int):
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


@router.post("/messages/")
async def create_message(messages: list[MessageBody]):
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
    target_message = next((m for m in messages if m["content"] == ratingbody.message), None)
    if not target_message:
        raise HTTPException(status_code=404, detail="Message not found for rating.")
    message_id = target_message["message_id"]
    rating_id = check_rating_exists( message_id)
    if ratingbody.sessionIdInt % 2 == 0:
        version = "GROUP-A"
    else:
        version = "GROUP-B"
    try:
        if rating_id:
            print(f"Rating already exists for message_id {message_id}, updating existing rating.")
            # Update the existing rating
            update_rating(rating_id, ratingbody.rating)
            return {"rating_id": rating_id, "message_id": message_id}
        else:
            rating_id = insert_rating(ratingbody.userId, ratingbody.rating, message_id, version)
            print(f"Rating with ID {rating_id} inserted into database for message_id {message_id}")
            return {"rating_id": rating_id, "message_id": message_id}
    except Exception as e:
        raise e