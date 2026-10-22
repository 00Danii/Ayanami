"""
Configuración unificada del firewall de Ayanami.

Reúne en un solo archivo (firewall_config.json) la lista blanca, el
registro de apps y los datos de referencia del gateway, y mantiene
backups automáticos con retención de las últimas 5 copias.

Uso desde systemd (timer programado):
    python firewall_config.py
"""
import glob
import json
import os
import socket
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = str(REPO_ROOT / "firewall_config.json")
BACKUP_DIR = str(REPO_ROOT / "backups")
APPS_FILE = str(REPO_ROOT / "apps_firewall.json")
WHITELIST_FILE = str(REPO_ROOT / "whitelist.json")
INSTALL_BACKUP_TIMER = str(REPO_ROOT / "systemd" / "install_backup_timer.sh")

CONFIG_VERSION = 1
RETENTION_BACKUPS = 5
BACKUP_PREFIX = "firewall_config-"
BACKUP_SUFFIX = ".json"


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
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return default or {}


def _write_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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
    apps_raw = _read_json(APPS_FILE)
    apps = {
        name: info for name, info in apps_raw.items()
        if isinstance(info, dict)
    }
    whitelist_raw = _read_json(WHITELIST_FILE, {"whitelist": []})
    whitelist = whitelist_raw.get("whitelist", [])
    if not isinstance(whitelist, list):
        whitelist = []
    whitelist_disabled = whitelist_raw.get("disabled", [])
    if not isinstance(whitelist_disabled, list):
        whitelist_disabled = []

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
        "whitelist_disabled": whitelist_disabled,
        "apps": apps,
    }
    return bundle


def load_config(path: str | None = None) -> dict:
    return _read_json(path or CONFIG_FILE)


def load_config_checked(path: str | None = None) -> tuple[dict, str]:
    """Lee un bundle y devuelve ``(config, error)``.

    A diferencia de ``load_config``, no oculta un JSON inválido: permite
    mostrar en la UI si el problema es un archivo truncado o corrupto en
    vez de informar simplemente que falta ``version``.
    """
    target = path or CONFIG_FILE
    if not os.path.exists(target):
        return {}, f"no existe el archivo {target}"
    try:
        with open(target) as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return {}, (
            f"JSON inválido en la línea {exc.lineno}, columna {exc.colno}: "
            f"{exc.msg}"
        )
    except (UnicodeDecodeError, OSError) as exc:
        return {}, f"no se pudo leer el archivo: {exc}"

    if not isinstance(data, dict):
        return {}, "el JSON no es un objeto"
    return data, ""


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
        return False, "falta el campo 'whitelist' (lista de entradas)"
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
# Backups automáticos con retención
# ─────────────────────────────────────────────────────────────

def _backup_stamp() -> str:
    """Marca de tiempo única para el nombre del backup."""
    return datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")


def _backup_path(stamp: str | None = None) -> str:
    stamp = stamp or _backup_stamp()
    return os.path.join(BACKUP_DIR, f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}")


def _backup_stem(path: str) -> str | None:
    name = os.path.basename(path)
    if not (name.startswith(BACKUP_PREFIX) and name.endswith(BACKUP_SUFFIX)):
        return None
    return name[len(BACKUP_PREFIX):-len(BACKUP_SUFFIX)]


def _valid_backup_stem(stem: str) -> bool:
    """Acepta backups nuevos con fecha/hora y los antiguos ``YYYY-MM``."""
    for fmt in ("%Y-%m-%d_%H%M%S_%f", "%Y-%m-%d_%H%M%S", "%Y-%m"):
        try:
            datetime.strptime(stem, fmt)
            return True
        except ValueError:
            pass
    return False


def save_backup(stamp: str | None = None) -> str | None:
    """Crea una copia válida con marca de tiempo en ``BACKUP_DIR``.

    Si el bundle canónico está incompleto o corrupto, genera uno nuevo
    desde los archivos vivos. La escritura es atómica: nunca deja una
    copia a medio escribir si falla el disco o los permisos.
    """
    config = load_config(CONFIG_FILE)
    ok, _ = validate_config(config)
    if not ok:
        config = build_bundle()
        if not os.path.exists(CONFIG_FILE):
            save_config(config)

    target = _backup_path(stamp)
    tmp = f"{target}.tmp"
    try:
        _write_json(tmp, config)
        os.replace(tmp, target)
        return target
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return None


def list_backups() -> list[dict]:
    """Lista los backups, del más nuevo al más viejo.

    Cada elemento trae ``bucket`` (identificador del archivo),
    ``path``, ``size`` (bytes) y ``mtime`` (timestamp). Se aceptan
    nombres nuevos con fecha/hora y los antiguos ``YYYY-MM``.
    """
    pattern = os.path.join(BACKUP_DIR, f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")
    backups = []
    for path in glob.glob(pattern):
        stem = _backup_stem(path)
        if not stem or not _valid_backup_stem(stem):
            continue
        try:
            stat = os.stat(path)
        except OSError:
            continue
        backups.append({
            "bucket": stem,
            "path": path,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        })
    return sorted(
        backups,
        key=lambda item: (item["mtime"], item["bucket"]),
        reverse=True,
    )


def prune_backups(keep: int = RETENTION_BACKUPS) -> list[str]:
    """Conserva los ``keep`` backups más recientes y borra el resto."""
    removed = []
    for info in list_backups()[keep:]:
        try:
            os.remove(info["path"])
            removed.append(info["path"])
        except OSError:
            pass
    return removed


def delete_backup(path: str) -> bool:
    """Borra un backup, solo si está dentro de BACKUP_DIR.

    La comprobación evita que un id manipulado desde la UI pueda borrar
    archivos fuera de la carpeta de respaldos.
    """
    target = os.path.realpath(path)
    root = os.path.realpath(BACKUP_DIR)
    if os.path.dirname(target) != root:
        return False
    stem = _backup_stem(target)
    if not stem or not _valid_backup_stem(stem):
        return False
    try:
        os.remove(target)
        return True
    except OSError:
        return False


def run_scheduled_backup() -> tuple[str | None, list[str]]:
    """Flujo completo del timer: crea un backup y aplica la retención."""
    target = save_backup()
    removed = prune_backups()
    return target, removed


# ─────────────────────────────────────────────────────────────
# CLI (usado por el systemd timer)
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    target, removed = run_scheduled_backup()
    print(f"[ayanami-backup] backup: {target or 'FAILED'}")
    if removed:
        print(f"[ayanami-backup] eliminados: {', '.join(removed)}")
    else:
        print("[ayanami-backup] sin backups viejos que limpiar")