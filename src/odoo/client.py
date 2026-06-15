import xmlrpc.client
from src.config import settings


class OdooClient:
    def __init__(self, email: str, password: str):
        self._url = settings.odoo_url
        self._db = settings.odoo_db
        self._email = email
        self._password = password
        self._uid: int | None = None

    @property
    def _common(self):
        return xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/common")

    @property
    def _models(self):
        return xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/object")

    def _get_uid(self) -> int:
        if self._uid is None:
            uid = self._common.authenticate(self._db, self._email, self._password, {})
            if not uid:
                raise PermissionError("Autenticación Odoo fallida")
            self._uid = uid
        return self._uid

    def execute(self, model: str, method: str, args: list, kwargs: dict | None = None) -> object:
        uid = self._get_uid()
        return self._models.execute_kw(
            self._db, uid, self._password,
            model, method, args, kwargs or {}
        )

    def search_read(self, model: str, domain: list, fields: list, limit: int = 50, order: str | None = None) -> list:
        kw: dict = {"fields": fields, "limit": limit}
        if order:
            kw["order"] = order
        return self.execute(model, "search_read", [domain], kw)

    def search(self, model: str, domain: list, limit: int = 50) -> list:
        return self.execute(model, "search", [domain], {"limit": limit})

    def read(self, model: str, ids: list, fields: list) -> list:
        return self.execute(model, "read", [ids], {"fields": fields})

    def create(self, model: str, values: dict) -> int:
        return self.execute(model, "create", [values])

    def write(self, model: str, ids: list, values: dict) -> bool:
        return self.execute(model, "write", [ids, values])

    def call(self, model: str, method: str, ids: list) -> object:
        return self.execute(model, method, [ids])

    def test_connection(self) -> dict:
        try:
            uid = self._get_uid()
            version = self._common.version()
            return {
                "ok": True,
                "uid": uid,
                "odoo_version": version.get("server_version", "unknown"),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


def odoo_from_token(token_payload: dict) -> OdooClient:
    return OdooClient(email=token_payload["email"], password=token_payload["pwd"])
