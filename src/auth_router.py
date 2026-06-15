from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.auth import authenticate_odoo, create_token

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
def login(req: LoginRequest):
    try:
        user = authenticate_odoo(req.email, req.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    token = create_token(
        uid=user["uid"],
        email=user["email"],
        password=user["password"],
        name=user["name"],
    )
    return {
        "token": token,
        "token_type": "Bearer",
        "user_name": user["name"],
        "user_email": user["email"],
        "expires_in_hours": 8,
        "usage": f'Configura en Heinzbot — API Key: Bearer {token}',
    }
