# routes/api.py
from fastapi import APIRouter, HTTPException
from service.database import (
    get_users, 
    get_selected_user, 
    insert_user, 
    get_selected_session, 
    insert_session,
    get_selected_messages,
    insert_messages,
    Message
)
from pydantic import BaseModel, EmailStr

class LoginBody(BaseModel):
    email: EmailStr
    password: str

class RegisterBody(BaseModel):
    username: str
    email: EmailStr
    password: str

class MessagesBody(BaseModel):
    messages: list[Message]

# Create a router instance
router = APIRouter()

# USER entrypoints

@router.get("/users/")
async def get_all_users():
    result = get_users()
    return result

@router.get("/user/{user_id}/")
async def get_user_by_user_id(user_id: int):
    result = get_selected_user(column_name="user_id", filter_value=user_id)
    return result

@router.post("/user/register/")
async def register(body: RegisterBody):
    try:
        result = insert_user(username=body.username, email=body.email, password=body.password)
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
        if user['password'] != body.password:
            raise HTTPException(status_code=401, detail="Incorrect password.")
        
        # Return success response
        return {"message": "Login successful!", "user_id": user['user_id']}
    
    except HTTPException as e:
        raise e  # Reraise HTTP exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error.")

# SESSION Entrypoints

@router.get("/session/{user_id}/")
async def get_session_by_user_id(user_id: int, filter_active_sessions: bool = False):
    result = get_selected_session(
        column_name="user_id", 
        filter_value=user_id, 
        filter_is_active=filter_active_sessions
    )
    return result

@router.post("/session/")
async def create_session(user_id: int, session_token: str, is_active: bool):
    result = insert_session(user_id=user_id, session_token=session_token, is_active=is_active)
    return result

# MESSAGE Entrypoints

@router.get("/messages/{session_id}/")
async def get_messages_by_session_id(session_id: int):
    result = get_selected_messages(column_name="session_id", filter_value=session_id)
    return result

@router.post("/messages/")
async def create_message(messages: list[Message]):
    result = insert_messages(messages=messages)
    return result