from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Select, RichLog

import os
import json
import subprocess

import network
import firewall_config
from firewall_ops import (
    get_dns_block_file,
    reset_apps_state,
    apply_whitelist,
    write_block_domains,
    save_whitelist,
)
from widgets.confirm_screen import ConfirmScreen
from widgets.path_picker import PathPicker


class ConfigTab(Vertical):
    def compose(self):
    
        with Vertical(classes="fw-card"):
            yield Label("Gateway / NAT", classes="fw-card-title")
            yield Label(
                "Configura el enrutamiento para que los dispositivos "
                "tengan salida a internet",
                classes="fw-card-desc"
            )
            with Horizontal(classes="fw-gw-row"):
                yield Select(
                    [],
                    prompt="Selecciona interfaz con internet",
                    id="cfg-nat-iface"
                )
                yield Button("Configurar Gateway", id="cfg-setup-nat", variant="success")
                yield Button("Ver Estado", id="cfg-show-status", variant="primary")
                yield Button("Limpiar Firewall", id="cfg-flush", variant="error")
                yield Select(
                    [("Guardar Config", "export"), ("Cargar Config", "import")],
                    id="cfg-backup",
                    prompt="Copia de Seguridad",
                )

        yield RichLog(id="cfg-log", markup=True, highlight=True)

    def on_mount(self):
        ifaces = network.get_interfaces_detailed()
        select = self.query_one("#cfg-nat-iface", Select)
        options = [
            (f"{d['iface']} ({d['state']})", d['iface'])
            for d in ifaces
        ]
        select.set_options(options)

    def _get_selected_interface(self):
        iface = getattr(self.app, "selected_interface", None)
        return iface

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "cfg-setup-nat":
            self.setup_gateway()
        elif bid == "cfg-show-status":
            self.show_status()
        elif bid == "cfg-flush":
            self.app.push_screen(
                ConfirmScreen(
                    "Se limpiarán todas las reglas de firewall,\n"
                    "se desbloquearán todas las apps y\n"
                    "se perderá la configuración del gateway.\n\n"
                    "Tendrás que configurar el gateway nuevamente.\n\n"
                    "¿Continuar?",
                    confirm_text="Limpiar"
                ),
                self.flush_all
            )

    def on_select_changed(self, event: Select.Changed):
        if event.select.id != "cfg-backup":
            return
        value = event.value
        if value == "export":
            self._request_export()
        elif value == "import":
            self._request_import()
        event.select.clear()

    def _request_export(self):
        self.app.push_screen(
            PathPicker(
                "Guardar Configuración",
                firewall_config.CONFIG_FILE,
                confirm_text="Guardar",
            ),
            self._do_export
        )

    def _request_import(self):
        self.app.push_screen(
            PathPicker(
                "Cargar Configuración",
                firewall_config.CONFIG_FILE,
                confirm_text="Cargar",
            ),
            self._pick_import_path
        )

    def _pick_import_path(self, path):
        if not path:
            return
        if not os.path.exists(path):
            self.app.notify("El archivo seleccionado no existe", severity="error")
            return
        self.app.push_screen(
            ConfirmScreen(
                f"Se cargará:\n\n{path}\n\n"
                "Se reaplicarán lista blanca, apps y gateway/NAT.\n"
                "Se sobrescribirá el estado actual.\n\n"
                "¿Continuar?",
                confirm_text="Cargar"
            ),
            lambda confirmed: self._import_config(confirmed, path)
        )

    def log(self, text: str):
        self.query_one("#cfg-log", RichLog).write(text)

    def run(self, cmd: str):
        self.log(f"[#565f89]$ {cmd}[/]")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.strip().splitlines():
                self.log(f"[#a9b1d6]{line}[/]")
        if result.returncode != 0 and result.stderr:
            for line in result.stderr.strip().splitlines():
                self.log(f"[#f7768e]{line}[/]")
        return result

    def setup_gateway(self):
        select = self.query_one("#cfg-nat-iface", Select)
        iface = select.value
        if iface is Select.NULL:
            self.app.notify("Selecciona la interfaz con internet", severity="error")
            return
        self.query_one("#cfg-log", RichLog).clear()

        lan_iface = self._get_selected_interface()
        dns_target = network.get_iface_ip(lan_iface)

        self.log(f"\n[#e0af68]━━━ Configuración del Gateway ━━━[/]")

        self.log(f"[#565f89]   Interfaz WAN : {iface}[/]")
        self.log(f"[#565f89]   Interfaz LAN : {lan_iface}[/]")

        # ─────────────────────────────────────────────
        # IP FORWARD
        # ─────────────────────────────────────────────

        self.log("[#7dcfff]◆ Habilitando reenvío de paquetes IPv4[/]")

        self.run("sysctl -w net.ipv4.ip_forward=1")
        try:
            with open("/etc/sysctl.conf", "r") as f:
                content = f.read()
            if "net.ipv4.ip_forward=1" not in content:
                with open("/etc/sysctl.conf", "a") as f:
                    f.write("\nnet.ipv4.ip_forward=1\n")
                self.log("[#9ece6a]  ✓ IP Forward habilitado de forma persistente en /etc/sysctl.conf[/]")
            else:
                self.log("[#9ece6a]  ✓ IP Forward ya estaba configurado[/]")

        except Exception as e:
            self.log(f"[#f7768e]  ✗ Error al configurar /etc/sysctl.conf: {e}[/]")

        # ─────────────────────────────────────────────
        # MASQUERADE
        # ─────────────────────────────────────────────

        self.log("[#7dcfff]◆ Configurando NAT (MASQUERADE)[/]")

        self.log(f"[#565f89]  → El tráfico de los clientes saldrá por {iface}[/]")

        self.run(
            f"iptables -t nat -C POSTROUTING -o {iface} -j MASQUERADE 2>/dev/null || "
            f"iptables -t nat -A POSTROUTING -o {iface} -j MASQUERADE"
        )

        self.log("[#9ece6a]  ✓ Regla MASQUERADE configurada[/]")

        # ─────────────────────────────────────────────
        # DNS
        # ─────────────────────────────────────────────

        self.log("[#7dcfff]◆ Configurando redirección DNS[/]")

        if not dns_target:
            self.log(
                f"[#f7768e]  ✗ No se pudo obtener la IP de la interfaz LAN "
                f"{lan_iface}[/]"
            )

            self.app.notify(
                "No se pudo obtener la IP de la interfaz LAN",
                severity="error"
            )

            return

        self.log(f"[#565f89]  → Interfaz DNS: {lan_iface}[/]")
        self.log(f"[#565f89]  → Dirección local: {dns_target}[/]")
        self.log("[#565f89]  → Las consultas DNS de los clientes serán redirigidas a AYANAMI[/]")

        for proto in ("udp", "tcp"):
            self.run(
                f"iptables -t nat -C PREROUTING -p {proto} --dport 53 "
                f"-j DNAT --to-destination {dns_target} 2>/dev/null || "
                f"iptables -t nat -A PREROUTING -p {proto} --dport 53 "
                f"-j DNAT --to-destination {dns_target}"
            )

            self.log(f"[#9ece6a]  ✓ DNS {proto.upper()} (puerto 53) redirigido[/]")

        # ─────────────────────────────────────────────
        # FINAL
        # ─────────────────────────────────────────────

        self.log("[#9ece6a]━━━ Gateway configurado correctamente ━━━[/]")

        self.log(f"[#565f89]   WAN → {iface}[/]")

        self.log(f"[#565f89]   LAN → {lan_iface} ({dns_target})[/]")

        self.log("[#565f89]   NAT → Activo[/]")

        self.log("[#565f89]   DNS → Redirección local activa[/]")

        try:
            firewall_config.update_gateway(iface, lan_iface, dns_target)
            self.log(
                "[#9ece6a]  ✓ Gateway guardado en firewall_config.json[/]"
            )
        except Exception as e:
            self.log(f"[#f7768e]  ✗ No se pudo guardar config: {e}[/]")

        self.app.notify(f"Gateway configurado en {iface}")

    def _do_export(self, path):
        """Guarda el estado actual (whitelist + apps + gateway) en la ruta
        elegida y crea un backup mensual inmediato."""
        if not path:
            return
        self.query_one("#cfg-log", RichLog).clear()
        self.log("\n[#e0af68]━━━ Guardar Configuración ━━━[/]")

        select = self.query_one("#cfg-nat-iface", Select)
        wan = select.value if select.value is not Select.NULL else ""
        lan = self._get_selected_interface() or ""
        dns_target = ""
        if lan:
            dns_target = network.get_iface_ip(lan) or ""

        bundle = firewall_config.build_bundle(
            wan_iface=wan,
            lan_iface=lan,
            dns_target=dns_target,
        )

        target = firewall_config.save_config(bundle, path=path)
        self.log(f"[#9ece6a]  ✓ Configuración guardada en {target}[/]")

        # Mantener la copia canónica al día para que el timer mensual
        # siempre respalde la configuración más reciente.
        if os.path.abspath(target) != os.path.abspath(firewall_config.CONFIG_FILE):
            firewall_config.save_config(bundle)
            self.log(
                f"[#565f89]  → Copia canónica también en "
                f"{firewall_config.CONFIG_FILE}[/]"
            )

        stats = bundle.get("stats", {})
        self.log(
            f"[#565f89]  → {stats.get('whitelist_count', 0)} IPs en lista blanca, "
            f"{stats.get('apps_count', 0)} apps, "
            f"{stats.get('blocked_count', 0)} bloqueadas[/]"
        )

        backup = firewall_config.save_backup()
        removed = firewall_config.prune_backups()
        if backup:
            self.log(f"[#9ece6a]  ✓ Backup mensual: {backup}[/]")
        if removed:
            self.log(
                f"[#565f89]  → Backups viejos eliminados: {len(removed)}[/]"
            )

        self.app.notify("Configuración guardada")

    def _import_config(self, confirmed: bool | None = None, path: str | None = None):
        if not confirmed:
            return
        source = path or firewall_config.CONFIG_FILE
        self.query_one("#cfg-log", RichLog).clear()
        self.log("\n[#e0af68]━━━ Cargar Configuración ━━━[/]")
        self.log(f"[#565f89]  → Origen: {source}[/]")

        config = firewall_config.load_config(source)
        if not config:
            self.log(f"[#f7768e]  ✗ {source} vacío o inválido[/]")
            self.app.notify(
                "El archivo de configuración está vacío o es inválido",
                severity="error",
            )
            return

        # ── Lista blanca ─────────────────────────────────
        whitelist = config.get("whitelist", [])
        save_whitelist(whitelist)
        self.log(
            f"[#9ece6a]  ✓ Lista blanca restaurada "
            f"({len(whitelist)} entradas)[/]"
        )

        # ── Apps ─────────────────────────────────────────
        apps = config.get("apps", {})
        with open(firewall_config.APPS_FILE, "w") as f:
            json.dump(apps, f, indent=2, ensure_ascii=False)
            f.write("\n")
        blocked_domains = []
        for info in apps.values():
            if info.get("blocked"):
                blocked_domains.extend(info.get("domains", []))
        self.log(
            f"[#9ece6a]  ✓ Registro de apps restaurado "
            f"({len(apps)} apps, {len(blocked_domains)} dominios bloqueados)[/]"
        )

        # ── Firewall: aplicar whitelist + bloqueo DNS ────
        self.log("[#7dcfff]◆ Aplicando reglas de lista blanca[/]")
        apply_whitelist()
        self.log("[#9ece6a]  ✓ Reglas de lista blanca aplicadas[/]")

        self.log("[#7dcfff]◆ Regenerando configuración de bloqueo DNS[/]")
        dns_conf = get_dns_block_file()
        if os.path.exists(dns_conf):
            os.remove(dns_conf)
        write_block_domains(blocked_domains)
        self.log(
            f"[#9ece6a]  ✓ Bloqueo DNS regenerado "
            f"({len(blocked_domains)} dominios)[/]"
        )

        # ── Gateway / NAT ────────────────────────────────
        gw = config.get("gateway", {})
        wan = gw.get("wan_iface", "")
        lan = gw.get("lan_iface", "")
        stored_target = gw.get("dns_target", "")
        if wan:
            self.log("[#7dcfff]◆ Reaplicando gateway[/]")
            self.run("sysctl -w net.ipv4.ip_forward=1")
            self.run(
                f"iptables -t nat -C POSTROUTING -o {wan} -j MASQUERADE 2>/dev/null || "
                f"iptables -t nat -A POSTROUTING -o {wan} -j MASQUERADE"
            )
            if lan:
                dns_target = network.get_iface_ip(lan) or stored_target
            else:
                dns_target = stored_target
            if dns_target:
                for proto in ("udp", "tcp"):
                    self.run(
                        f"iptables -t nat -C PREROUTING -p {proto} --dport 53 "
                        f"-j DNAT --to-destination {dns_target} 2>/dev/null || "
                        f"iptables -t nat -A PREROUTING -p {proto} --dport 53 "
                        f"-j DNAT --to-destination {dns_target}"
                    )
                self.log(
                    f"[#9ece6a]  ✓ Gateway reaplicado: WAN={wan} "
                    f"DNS→{dns_target}[/]"
                )
            else:
                self.log(
                    "[#f7768e]  ✗ Sin DNS target: no se pudo reaplicar "
                    "la redirección DNS[/]"
                )
        else:
            self.log("[#565f89]  → Sin gateway guardado, se omite[/]")

        # ── Aplicar cambios y refrescar vistas ────────────
        self.log("[#7dcfff]◆ Reiniciando NetworkManager[/]")
        self.run("systemctl restart NetworkManager")
        self.log("[#9ece6a]  ✓ Cambios aplicados[/]")
        self.log("[#9ece6a]━━━ Configuración cargada ━━━[/]")

        apps_tab = self.screen.query_one("#fw-panel-apps")
        if hasattr(apps_tab, "refresh_apps"):
            apps_tab.refresh_apps()
        rules_tab = self.screen.query_one("#fw-panel-rules")
        if hasattr(rules_tab, "refresh_list"):
            rules_tab.refresh_list()

        self.app.notify("Configuración cargada y aplicada")

    def show_status(self):
        dns_conf = get_dns_block_file()
        self.query_one("#cfg-log", RichLog).clear()
        self.log("\n[#e0af68]━━━ IP FORWARD ━━━[/]")
        self.run("sysctl net.ipv4.ip_forward")
        self.log("\n[#e0af68]━━━ REGLAS DNS ━━━[/]")
        if os.path.exists(dns_conf):
            with open(dns_conf) as f:
                content = f.read().strip()
                self.log(f"[#a9b1d6]{content or 'Sin reglas'}[/]")
        else:
            self.log("[#565f89]Sin reglas[/]")
        self.log("\n[#e0af68]━━━ FORWARD ━━━[/]")
        self.run("iptables -L FORWARD -n --line-numbers")
        self.log("\n[#e0af68]━━━ NAT ━━━[/]")
        self.run("iptables -t nat -L -n --line-numbers")

    def flush_all(self, confirmed: bool | None = None):
        if not confirmed:
            return
        dns_conf = get_dns_block_file()
        self.query_one("#cfg-log", RichLog).clear()
        self.log("\n[#f7768e]━━━ Limpiando firewall ━━━[/]")
        if os.path.exists(dns_conf):
            os.remove(dns_conf)
            self.log("[#9ece6a]✓ Reglas DNS eliminadas[/]")
        self.log("[#7dcfff]◆ Limpiando iptables FORWARD[/]")
        self.run("iptables -F FORWARD")
        self.log("[#7dcfff]◆ Limpiando iptables NAT[/]")
        self.run("iptables -t nat -F")
        self.log("[#7dcfff]◆ Sincronizando estado de apps[/]")
        reset_apps_state()
        self.log("[#9ece6a]✓ Apps desbloqueadas en config[/]")
        self.log("[#9ece6a]━━━ Firewall limpiado ━━━[/]")
        self.log("[#7dcfff]◆ Cerrando conexiones activas[/]")
        self.run("conntrack -F")
        apps_tab = self.screen.query_one("#fw-panel-apps")
        if hasattr(apps_tab, "refresh_apps"):
            apps_tab.refresh_apps()
        self.app.notify("Firewall limpiado")
