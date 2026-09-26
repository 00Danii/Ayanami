"""
Configuración unificada del firewall de Ayanami.

Reúne en un solo archivo (firewall_config.json) la lista blanca, el
registro de apps y los datos de referencia del gateway, y mantiene
copias de seguridad mensuales con retención de 3 meses.

Uso desde systemd (timer mensual):
    python firewall_config.py
"""
import glob
import json
import os
import socket
from datetime import datetime
from pathlib import Path

CONFIG_FILE = str(Path(__file__).resolve().parent.parent / "firewall_config.json")
BACKUP_DIR = os.path.join(os.path.dirname(CONFIG_FILE), "backups")
APPS_FILE = os.path.join(os.path.dirname(CONFIG_FILE), "apps_firewall.json")
WHITELIST_FILE = os.path.join(os.path.dirname(CONFIG_FILE), "whitelist.json")

CONFIG_VERSION = 1
RETENTION_MONTHS = 3


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _read_json(path: str, default=None) -> dict:
    if not os.path.exists(path):
        return default or {}
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else (default or {})
    except (json.JSONDecodeError, OSError):
        return default or {}


def _write_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _month_bucket() -> str:
    return datetime.now().strftime("%Y-%m")


# ─────────────────────────────────────────────────────────────
# Config: guardar / cargar
# ─────────────────────────────────────────────────────────────

def build_bundle(
    wan_iface: str = "",
    lan_iface: str = "",
    dns_target: str = "",
    applied_at: str = "",
) -> dict:
    """Arma el bundle completo con el estado actual.

    La lista blanca y las apps se leen de los archivos vivos; el gateway
    se fusiona con lo que ya esté guardado (los valores pasados por
    parámetro tienen prioridad, y solo son datos de referencia).
    """
    apps = _read_json(APPS_FILE)
    whitelist_raw = _read_json(WHITELIST_FILE, {"whitelist": []})
    whitelist = whitelist_raw.get("whitelist", [])

    stored = load_config()
    gw = stored.get("gateway", {})

    domain_total = sum(len(info.get("domains", [])) for info in apps.values())

    bundle = {
        "version": CONFIG_VERSION,
        "exported_at": _now_iso(),
        "hostname": socket.gethostname(),
        "gateway": {
            "wan_iface": wan_iface or gw.get("wan_iface", ""),
            "lan_iface": lan_iface or gw.get("lan_iface", ""),
            "dns_target": dns_target or gw.get("dns_target", ""),
            "applied_at": applied_at or gw.get("applied_at", ""),
        },
        "stats": {
            "whitelist_count": len(whitelist),
            "apps_count": len(apps),
            "blocked_count": sum(1 for i in apps.values() if i.get("blocked")),
            "domains_count": domain_total,
        },
        "whitelist": whitelist,
        "apps": apps,
    }
    return bundle


def load_config(path: str | None = None) -> dict:
    return _read_json(path or CONFIG_FILE)


def validate_config(cfg: dict) -> tuple[bool, str]:
    """Comprueba que un bundle cargado sea realmente una configuración
    de Ayanami. Devuelve (ok, razón). No debe aplicarse nada si no es ok."""
    if not isinstance(cfg, dict):
        return False, "no es un objeto JSON válido"
    if "version" not in cfg:
        return False, "falta el campo 'version'"
    if not isinstance(cfg.get("apps"), dict):
        return False, "falta el campo 'apps' (dict de aplicaciones)"
    if not isinstance(cfg.get("whitelist"), list):
        return False, "falta el campo 'whitelist' (lista de IPs)"
    return True, ""


def save_config(bundle: dict, path: str | None = None) -> str:
    target = path or CONFIG_FILE
    _write_json(target, bundle)
    return target


def update_gateway(wan_iface: str, lan_iface: str, dns_target: str) -> str:
    """Persiste la configuración del gateway recién aplicada.

    Guarda también applied_at para saber cuándo se configuró por última vez.
    """
    config = load_config()
    config["gateway"] = {
        "wan_iface": wan_iface,
        "lan_iface": lan_iface,
        "dns_target": dns_target,
        "applied_at": _now_iso(),
    }
    return save_config(config)


# ─────────────────────────────────────────────────────────────
# Backups mensuales con retención
# ─────────────────────────────────────────────────────────────

def _backup_path(month: str | None = None) -> str:
    bucket = month or _month_bucket()
    return os.path.join(BACKUP_DIR, f"firewall_config-{bucket}.json")


def save_backup(month: str | None = None) -> str | None:
    """Copia el firewall_config.json al bucket mensual (YYYY-MM).

    Si el archivo de configuración no existe todavía, primero lo genera
    con el estado actual. Devuelve la ruta del backup o None si no pudo.
    """
    if not os.path.exists(CONFIG_FILE):
        save_config(build_bundle())

    target = _backup_path(month)
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(CONFIG_FILE) as src, open(target, "w") as dst:
            dst.write(src.read())
        return target
    except OSError:
        return None


def prune_backups(keep: int = RETENTION_MONTHS) -> list[str]:
    """Borra los backups más viejos que los últimos `keep` meses.

    Ordena por bucket mensual (YYYY-MM) y elimina el resto.
    Devuelve la lista de archivos eliminados.
    """
    pattern = os.path.join(BACKUP_DIR, "firewall_config-*.json")
    removed = []
    buckets = set()
    for path in glob.glob(pattern):
        name = os.path.basename(path)
        try:
            bucket = name.replace("firewall_config-", "").replace(".json", "")
            datetime.strptime(bucket, "%Y-%m")
        except ValueError:
            continue
        buckets.add((bucket, path))

    ordered = sorted(buckets, key=lambda x: x[0], reverse=True)
    for _, path in ordered[keep:]:
        try:
            os.remove(path)
            removed.append(path)
        except OSError:
            pass
    return removed


def run_monthly_backup() -> list[str]:
    """Flujo completo del timer mensual: backup + limpieza."""
    target = save_backup()
    removed = prune_backups()
    return [target] if target else removed


# ─────────────────────────────────────────────────────────────
# CLI (usado por el systemd timer)
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    target = save_backup()
    removed = prune_backups()
    print(f"[ayanami-backup] backup: {target or 'FAILED'}")
    if removed:
        print(f"[ayanami-backup] eliminados: {', '.join(removed)}")
    else:
        print("[ayanami-backup] sin backups viejos que limpiar")