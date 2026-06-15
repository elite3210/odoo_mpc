from fastapi import FastAPI
from src.mcp.protocol import router as mcp_router
from src.auth_router import router as auth_router

app = FastAPI(title="Odoo MCP Server", version="1.0.0", docs_url="/docs")

app.include_router(auth_router)
app.include_router(mcp_router)


@app.get("/health")
def health():
    from src.config import settings
    import xmlrpc.client
    try:
        common = xmlrpc.client.ServerProxy(f"{settings.odoo_url}/xmlrpc/2/common")
        version = common.version()
        odoo_ok = True
        odoo_version = version.get("server_version", "unknown")
    except Exception:
        odoo_ok = False
        odoo_version = None

    return {
        "status": "ok" if odoo_ok else "degraded",
        "odoo_connected": odoo_ok,
        "odoo_version": odoo_version,
        "server_version": "1.0.0",
    }
