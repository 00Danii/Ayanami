"""
Configuración unificada del firewall de Ayanami.

Reúne en un solo archivo (firewall_config.json) la lista blanca, el
registro de apps, los datos de referencia del gateway y el contenido de
/etc/dnsmasq.conf, y mantiene backups automáticos con retención de las
últimas 5 copias.

Uso desde systemd (timer programado):
    python firewall_config.py
"""
import glob
import json
import os
import shutil
import socket
import stat
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = str(REPO_ROOT / "firewall_config.json")
BACKUP_DIR = str(REPO_ROOT / "backups")
APPS_FILE = str(REPO_ROOT / "apps_firewall.json")
WHITELIST_FILE = str(REPO_ROOT / "whitelist.json")
DNSMASQ_CONF = "/etc/dnsmasq.conf"
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
# dnsmasq.conf dentro del bundle
# ─────────────────────────────────────────────────────────────

def read_dnsmasq_config(path: str | None = None) -> dict:
    """Lee ``/etc/dnsmasq.conf`` para incluirlo en un backup.

    El contenido se guarda como texto con su codificación para que el JSON sea
    legible. UTF-8 es el caso normal; si falla, latin-1 conserva cualquier byte
    y permite reconstruir el archivo exactamente al restaurar.
    """
    target = path or DNSMASQ_CONF
    payload = {
        "path": target,
        "included_at": _now_iso(),
    }

    try:
        with open(target, "rb") as handle:
            raw = handle.read()
    except FileNotFoundError:
        payload.update({
            "available": False,
            "error": f"no existe {target}",
        })
        return payload
    except OSError as exc:
        payload.update({
            "available": False,
            "error": f"no se pudo leer {target}: {exc}",
        })
        return payload

    try:
        content = raw.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        content = raw.decode("latin-1")
        encoding = "latin-1"

    payload.update({
        "available": True,
        "encoding": encoding,
        "size": len(raw),
        "content": content,
    })
    return payload


def dnsmasq_payload_bytes(payload: dict) -> tuple[bytes | None, str]:
    """Convierte el bloque ``dnsmasq`` de un bundle a bytes.

    Devuelve ``(bytes, "")`` o ``(None, error)``. El campo ``path`` del JSON
    es solo informativo: la restauración siempre usa ``DNSMASQ_CONF``.
    """
    if not isinstance(payload, dict):
        return None, "el campo 'dnsmasq' no es un objeto"

    content = payload.get("content")
    if not isinstance(content, str):
        reason = payload.get("error")
        return None, str(reason or "la copia no incluye el contenido de dnsmasq.conf")

    encoding = payload.get("encoding") or "utf-8"
    if encoding not in ("utf-8", "latin-1"):
        return None, f"codificación no soportada para dnsmasq.conf: {encoding}"

    try:
        return content.encode(encoding), ""
    except UnicodeEncodeError as exc:
        return None, (
            f"el contenido de dnsmasq.conf no se puede codificar en "
            f"{encoding}: {exc}"
        )


def restore_dnsmasq(
    payload: dict,
    target: str | None = None,
) -> tuple[bool, str]:
    """Restaura ``dnsmasq.conf`` de forma validada y atómica.

    Escribe un temporal, ejecuta ``dnsmasq --test``, conserva la versión actual
    en ``<target>.ayanami.bak`` y solo entonces reemplaza el archivo. Si la
    validación falla, el archivo real no se toca.

    Devuelve ``(restaurado, aviso)``. ``restaurado`` es ``True`` si el archivo
    quedó escrito; ``aviso`` describe un problema no fatal (por ejemplo, que
    systemd no pudo reiniciar dnsmasq) o un error fatal si ``restaurado`` es
    ``False``.
    """
    raw, error = dnsmasq_payload_bytes(payload)
    if error:
        return False, error

    target = os.path.realpath(target or DNSMASQ_CONF)
    directory = os.path.dirname(target) or "."
    tmp_path = None
    written = False
    warning = ""

    try:
        fd, tmp_path = tempfile.mkstemp(
            prefix=".dnsmasq.conf.ayanami-restore-",
            dir=directory,
        )
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())

        try:
            original_stat = os.stat(target)
        except FileNotFoundError:
            original_stat = None
        except OSError as exc:
            return False, f"no se pudo leer {target}: {exc}"

        if original_stat is not None:
            os.chmod(tmp_path, stat.S_IMODE(original_stat.st_mode))
            try:
                os.chown(tmp_path, original_stat.st_uid, original_stat.st_gid)
            except (AttributeError, PermissionError):
                pass
        else:
            os.chmod(tmp_path, 0o644)

        try:
            test = subprocess.run(
                ["dnsmasq", "--test", "-C", tmp_path],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=10,
            )
        except FileNotFoundError:
            return False, "no se encontró el comando dnsmasq"
        except subprocess.TimeoutExpired:
            return False, "dnsmasq --test agotó el tiempo de espera"
        except OSError as exc:
            return False, f"no se pudo ejecutar dnsmasq --test: {exc}"

        test_output = (test.stdout + test.stderr).strip()
        if test.returncode != 0:
            return False, (
                test_output
                or f"dnsmasq --test salió con código {test.returncode}"
            )

        if original_stat is not None:
            try:
                shutil.copy2(target, target + ".ayanami.bak")
            except OSError as exc:
                warning = f"no se pudo crear {target}.ayanami.bak: {exc}"

        os.replace(tmp_path, target)
        written = True

        try:
            restart = subprocess.run(
                ["systemctl", "restart", "dnsmasq"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=30,
            )
        except FileNotFoundError:
            return True, "archivo restaurado, pero no se encontró systemctl"
        except subprocess.TimeoutExpired:
            return True, (
                "archivo restaurado, pero systemctl restart agotó el tiempo "
                "de espera"
            )
        except OSError as exc:
            return True, (
                f"archivo restaurado, pero no se pudo reiniciar dnsmasq: {exc}"
            )

        restart_output = (restart.stdout + restart.stderr).strip()
        if restart.returncode != 0:
            detail = restart_output or (
                f"systemctl restart salió con código {restart.returncode}"
            )
            return True, f"archivo restaurado, pero dnsmasq no se reinició: {detail}"

        return True, warning
    except OSError as exc:
        return False, f"no se pudo restaurar {target}: {exc}"
    finally:
        if not written and tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


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
    if not isinstance(gw, dict):
        gw = {}

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
        "dnsmasq": read_dnsmasq_config(),
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


def get_saved_gateway(path: str | None = None) -> dict:
    """Devuelve el gateway persistido, nunca valores inferidos de la UI."""
    stored = load_config(path)
    gateway = stored.get("gateway", {})
    return gateway if isinstance(gateway, dict) else {}


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
    if "dnsmasq" in cfg:
        dnsmasq = cfg.get("dnsmasq")
        if not isinstance(dnsmasq, dict):
            return False, "el campo 'dnsmasq' debe ser un objeto"
        if "content" in dnsmasq and not isinstance(dnsmasq.get("content"), str):
            return False, "el contenido de 'dnsmasq' debe ser texto"
        encoding = dnsmasq.get("encoding", "utf-8")
        if encoding not in ("utf-8", "latin-1"):
            return False, f"codificación de 'dnsmasq' no soportada: {encoding!r}"
        if isinstance(dnsmasq.get("content"), str):
            _raw, content_error = dnsmasq_payload_bytes(dnsmasq)
            if content_error:
                return False, content_error
    return True, ""


def save_config(bundle: dict, path: str | None = None) -> str:
    """Escribe un bundle de forma atómica (``.tmp`` + ``os.replace``)."""
    target = path or CONFIG_FILE
    tmp = f"{target}.tmp"
    try:
        _write_json(tmp, bundle)
        os.replace(tmp, target)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return target


def update_gateway(wan_iface: str, lan_iface: str, dns_target: str) -> str:
    """Persiste la configuración del gateway recién aplicada.

    Guarda también applied_at para saber cuándo se configuró por última vez.
    Si el canónico falta o está incompleto, se reconstruye antes de escribir
    para no dejar un JSON sin ``version``/``apps``/``whitelist``.
    """
    config = load_config()
    ok, _ = validate_config(config)
    if not ok:
        config = build_bundle()

    config["gateway"] = {
        "wan_iface": wan_iface or "",
        "lan_iface": lan_iface or "",
        "dns_target": dns_target or "",
        "applied_at": _now_iso(),
    }
    config["dnsmasq"] = read_dnsmasq_config()
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
    desde los archivos vivos. En cualquier caso refresca el bloque
    ``dnsmasq`` desde ``/etc/dnsmasq.conf`` para que la copia incluya su
    contenido actual. La escritura es atómica: nunca deja una copia a medio
    escribir si falla el disco o los permisos.
    """
    config = load_config(CONFIG_FILE)
    ok, _ = validate_config(config)
    if not ok:
        config = build_bundle()
        if not os.path.exists(CONFIG_FILE):
            save_config(config)
    else:
        config["dnsmasq"] = read_dnsmasq_config()

    target = _backup_path(stamp)
    try:
        return save_config(config, target)
    except OSError:
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