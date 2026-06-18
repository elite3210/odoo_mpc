import datetime
import json
import math
import os
import xmlrpc.client

from src.audit import log_write
from src.config import settings
from src.odoo.client import OdooClient

# Lima, Perú — UTC-5 sin horario de verano
LIMA_UTC_OFFSET = -5


# ── Utilidades GPS ────────────────────────────────────────────────────────────

def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _load_work_centers() -> list:
    path = os.path.abspath(settings.work_centers_path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _nearest_center(latitude: float, longitude: float) -> tuple[dict, float]:
    centers = _load_work_centers()
    best = min(centers, key=lambda c: _haversine_meters(latitude, longitude, c["latitude"], c["longitude"]))
    distance = _haversine_meters(latitude, longitude, best["latitude"], best["longitude"])
    return best, round(distance, 1)


# ── Utilidades de tiempo ──────────────────────────────────────────────────────

def _utc_now_str() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _lima_now() -> datetime.datetime:
    return datetime.datetime.utcnow() + datetime.timedelta(hours=LIMA_UTC_OFFSET)


def _parse_odoo_dt(dt_str: str) -> datetime.datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Formato de fecha no reconocido: {dt_str}")


def _to_lima(dt_utc: datetime.datetime) -> datetime.datetime:
    return dt_utc + datetime.timedelta(hours=LIMA_UTC_OFFSET)


def _today_range_utc() -> tuple[str, str]:
    lima_midnight = _lima_now().replace(hour=0, minute=0, second=0, microsecond=0)
    utc_start = lima_midnight - datetime.timedelta(hours=LIMA_UTC_OFFSET)
    utc_end = utc_start + datetime.timedelta(days=1)
    return utc_start.strftime("%Y-%m-%d %H:%M:%S"), utc_end.strftime("%Y-%m-%d %H:%M:%S")


# ── Odoo ──────────────────────────────────────────────────────────────────────

def _get_employee(odoo: OdooClient) -> dict | None:
    uid = odoo._get_uid()
    results = odoo.search_read(
        "hr.employee", [["user_id", "=", uid]],
        fields=["id", "name"], limit=1,
    )
    return results[0] if results else None


def _open_attendance(odoo: OdooClient, employee_id: int) -> dict | None:
    records = odoo.search_read(
        "hr.attendance",
        [["employee_id", "=", employee_id], ["check_out", "=", False]],
        fields=["id", "check_in"], limit=1,
    )
    return records[0] if records else None


# ── Tools MCP ─────────────────────────────────────────────────────────────────

def check_in_attendance(odoo: OdooClient, user_email: str, latitude: float, longitude: float) -> str:
    center, distance = _nearest_center(latitude, longitude)

    if distance > center["radius_meters"]:
        return (
            f"Entrada NO registrada — fuera del área permitida.\n\n"
            f"Sede más cercana: {center['name']}\n"
            f"Tu distancia: {distance}m  |  Máximo: {center['radius_meters']}m\n\n"
            f"Acércate a la sede e intenta de nuevo."
        )

    employee = _get_employee(odoo)
    if not employee:
        return "No encontré un empleado vinculado a tu usuario de Odoo. Contacta a Recursos Humanos."

    open_att = _open_attendance(odoo, employee["id"])
    if open_att:
        hora = _to_lima(_parse_odoo_dt(open_att["check_in"])).strftime("%H:%M")
        return (
            f"Ya tienes una entrada registrada a las {hora} (Lima) sin salida aún.\n"
            f"Para registrar tu salida di: 'registra mi salida'."
        )

    try:
        att_id = odoo.create("hr.attendance", {
            "employee_id": employee["id"],
            "check_in": _utc_now_str(),
        })
        log_write("check_in_attendance", {
            "user": user_email, "employee": employee["name"],
            "lat": latitude, "lon": longitude,
            "sede": center["name"], "distancia_m": distance,
        }, {"att_id": att_id})
        hora = _lima_now().strftime("%H:%M")
        return (
            f"Entrada registrada.\n\n"
            f"Empleado: {employee['name']}\n"
            f"Hora: {hora} (Lima)\n"
            f"Sede: {center['name']}  (a {distance}m del centro)"
        )
    except xmlrpc.client.Fault as e:
        log_write("check_in_attendance", {"user": user_email}, str(e), is_error=True)
        return f"Error de Odoo al registrar entrada: {e.faultString}"


def check_out_attendance(odoo: OdooClient, user_email: str, latitude: float, longitude: float) -> str:
    center, distance = _nearest_center(latitude, longitude)

    if distance > center["radius_meters"]:
        return (
            f"Salida NO registrada — fuera del área permitida.\n\n"
            f"Sede más cercana: {center['name']}\n"
            f"Tu distancia: {distance}m  |  Máximo: {center['radius_meters']}m"
        )

    employee = _get_employee(odoo)
    if not employee:
        return "No encontré un empleado vinculado a tu usuario de Odoo. Contacta a Recursos Humanos."

    open_att = _open_attendance(odoo, employee["id"])
    if not open_att:
        return (
            f"No tienes una entrada registrada hoy.\n"
            f"Registra primero tu entrada diciendo: 'registra mi entrada'."
        )

    try:
        now_utc = _utc_now_str()
        odoo.write("hr.attendance", [open_att["id"]], {"check_out": now_utc})
        log_write("check_out_attendance", {
            "user": user_email, "employee": employee["name"],
            "lat": latitude, "lon": longitude,
            "sede": center["name"], "distancia_m": distance,
        }, {"att_id": open_att["id"], "check_out": now_utc})

        entrada = _to_lima(_parse_odoo_dt(open_att["check_in"]))
        salida = _lima_now()
        trabajado = salida - entrada
        horas = int(trabajado.total_seconds() // 3600)
        minutos = int((trabajado.total_seconds() % 3600) // 60)

        return (
            f"Salida registrada.\n\n"
            f"Empleado: {employee['name']}\n"
            f"Entrada: {entrada.strftime('%H:%M')}  →  Salida: {salida.strftime('%H:%M')} (Lima)\n"
            f"Tiempo trabajado: {horas}h {minutos}m\n"
            f"Sede: {center['name']}"
        )
    except xmlrpc.client.Fault as e:
        log_write("check_out_attendance", {"user": user_email}, str(e), is_error=True)
        return f"Error de Odoo al registrar salida: {e.faultString}"


def get_attendance_status(odoo: OdooClient, user_email: str = "") -> str:
    employee = _get_employee(odoo)
    if not employee:
        return "No encontré un empleado vinculado a tu usuario de Odoo."

    start_utc, end_utc = _today_range_utc()
    records = odoo.search_read(
        "hr.attendance",
        [
            ["employee_id", "=", employee["id"]],
            ["check_in", ">=", start_utc],
            ["check_in", "<", end_utc],
        ],
        fields=["check_in", "check_out", "worked_hours"],
        order="check_in asc",
        limit=10,
    )

    fecha_lima = _lima_now().strftime("%d/%m/%Y")

    if not records:
        return f"{employee['name']} no tiene registros de asistencia hoy ({fecha_lima})."

    lines = [f"Asistencia de hoy — {employee['name']} ({fecha_lima}):\n"]
    total_segundos = 0.0
    activo = False

    for r in records:
        entrada = _to_lima(_parse_odoo_dt(r["check_in"]))
        if r["check_out"]:
            salida = _to_lima(_parse_odoo_dt(r["check_out"]))
            trabajado = (r.get("worked_hours") or 0) * 3600
            total_segundos += trabajado
            h = int(trabajado // 3600)
            m = int((trabajado % 3600) // 60)
            lines.append(f"  {entrada.strftime('%H:%M')} → {salida.strftime('%H:%M')}  ({h}h {m}m)")
        else:
            activo = True
            ahora = _lima_now()
            transcurrido = (ahora - entrada).total_seconds()
            total_segundos += transcurrido
            h = int(transcurrido // 3600)
            m = int((transcurrido % 3600) // 60)
            lines.append(f"  {entrada.strftime('%H:%M')} → EN CURSO  ({h}h {m}m)")

    th = int(total_segundos // 3600)
    tm = int((total_segundos % 3600) // 60)
    lines.append(f"\nTotal hoy: {th}h {tm}m")
    lines.append(f"Estado: {'TRABAJANDO' if activo else 'FUERA'}")

    return "\n".join(lines)
