import datetime
import jwt
import xmlrpc.client
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config import settings

_bearer = HTTPBearer()


def authenticate_odoo(email: str, password: str) -> dict:
    """
    Verifica credenciales contra Odoo. Retorna datos del usuario o lanza ValueError.
    """
    try:
        common = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/common")
        uid = common.authenticate(settings.odoo_db, email, password, {})
        if not uid:
            raise ValueError("Credenciales incorrectas")

        models = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/object")
        users = models.execute_kw(
            settings.odoo_db, uid, password,
            "res.users", "read", [[uid]],
            {"fields": ["name", "email", "login"]}
        )
        user = users[0] if users else {"name": email, "email": email, "login": email}
        return {"uid": uid, "name": user["name"], "email": email, "password": password}
    except xmlrpc.client.Fault as e:
        raise ValueError(f"Error de Odoo: {e.faultString}")
    except ConnectionRefusedError:
        raise ValueError("No se puede conectar al servidor Odoo")


def create_token(uid: int, email: str, password: str, name: str) -> str:
    payload = {
        "uid": uid,
        "email": email,
        "pwd": password,
        "name": name,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado — vuelve a hacer login")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


def require_token(credentials: HTTPAuthorizationCredentials = Security(_bearer)) -> dict:
    return decode_token(credentials.credentials)
