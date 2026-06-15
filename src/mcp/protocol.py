from fastapi import APIRouter, Depends
from src.auth import require_token
from src.odoo.client import odoo_from_token
from src.mcp.tools.registry import TOOL_DEFINITIONS, TOOL_HANDLERS

router = APIRouter()

MCP_VERSION = "2025-03-26"
SERVER_INFO = {"name": "odoo-mcp", "version": "1.0.0"}


def _ok(result: object, req_id) -> dict:
    return {"jsonrpc": "2.0", "result": result, "id": req_id}


def _err(code: int, message: str, req_id) -> dict:
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": req_id}


@router.post("/mcp")
async def mcp_endpoint(body: dict, token: dict = Depends(require_token)):
    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    if method == "initialize":
        return _ok({
            "protocolVersion": MCP_VERSION,
            "serverInfo": SERVER_INFO,
            "capabilities": {"tools": {}},
        }, req_id)

    if method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": req_id}

    if method == "tools/list":
        return _ok({"tools": TOOL_DEFINITIONS}, req_id)

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return _ok({
                "content": [{"type": "text", "text": f'Herramienta "{tool_name}" no encontrada.'}],
                "isError": True,
            }, req_id)

        try:
            odoo = odoo_from_token(token)
            text = handler(odoo=odoo, user_email=token["email"], **arguments)
            return _ok({
                "content": [{"type": "text", "text": text}],
                "isError": False,
            }, req_id)
        except TypeError as e:
            return _ok({"content": [{"type": "text", "text": f"Parámetros inválidos: {e}"}], "isError": True}, req_id)
        except Exception as e:
            return _ok({"content": [{"type": "text", "text": f"Error interno: {e}"}], "isError": True}, req_id)

    return _err(-32601, f'Método "{method}" no soportado.', req_id)
