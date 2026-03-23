import os
from pathlib import Path
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Any
from dotenv import load_dotenv

from service.database import get_selected_user

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_TOKEN_EXPIRATION_TIME = int(os.getenv("JWT_EXPIRATION_TIME", "60"))


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/login/")


class AuthorizationService:
    def __init__(self):
        self.JWT_SECRET = JWT_SECRET_KEY
        self.JWT_ALGORITHM = JWT_ALGORITHM
        self.JWT_EXPIRATION_TIME = JWT_TOKEN_EXPIRATION_TIME

    def create_token(self, user_id: int, email: str, temporary_user: bool) -> str:
        now: datetime = datetime.now(tz=timezone.utc)
        expire: datetime = now + timedelta(minutes=self.JWT_EXPIRATION_TIME)

        payload: Dict[str, Any] = {
            "user_id": user_id,
            "email": email,
            "exp": expire,
            "temporary_user": temporary_user,
        }
        token = jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)
        return token

    def decode_token(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self.JWT_SECRET,
                algorithms=[self.JWT_ALGORITHM],
                options={"require_exp": True},
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def get_token_data(self, token: str = Depends(oauth2_scheme)):
        """
        FastAPI dependency to:
         1. Validate & decode the JWT.
         2. Load the user from the database.
         3. Return the user dict (or raise 401).
        """
        data = self.decode_token(token)
        try:
            user = get_selected_user(
                column_name="user_id", filter_value=data["user_id"]
            )
            user["temporary_user"] = data.get("temporary_user")
        except KeyError:
            raise HTTPException(
                status_code=401,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
