import json
import datetime
from src.config import settings


def log_write(tool_name: str, arguments: dict, result: dict | str, is_error: bool = False) -> None:
    entry = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "tool": tool_name,
        "args": arguments,
        "result": result if isinstance(result, (dict, list)) else str(result),
        "error": is_error,
    }
    with open(settings.audit_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
