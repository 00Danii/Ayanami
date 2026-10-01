import json
import os
from pathlib import Path

from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, Switch, Input, Select

from views.firewall.app_modal import AppModal, APP_TYPES
from widgets.app_row import AppRow
from widgets.clickable_label import ClickableLabel
from widgets.confirm_screen import ConfirmScreen
from firewall_ops import (
    write_block_domains,
    remove_block_domains,
    apply_changes,
)


APPS_FILE = str(Path(__file__).resolve().parent.parent.parent.parent / "apps_firewall.json")

# ── Rendimiento ────────────────────────────────────────────
# Con muchas apps registradas el coste de pintar la lista crece: cada
# AppRow crea ~13 widgets. Por eso las filas se montan de una sola vez
# (mount(*filas)), se muestran de a PAGINADO_FILAS y se posterga la carga
# hasta que el usuario abre la pestaña (carga diferida).
PAGINADO_FILAS = 25
BUSQUEDA_DELAY = 0.25


class AppsTab(Vertical):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._apply_seq = 0
        self._search_seq = 0
        self._pagina = PAGINADO_FILAS
        self._loaded = False

    def compose(self):
        with Horizontal(classes="fw-apps-toolbar"):
            yield Input(placeholder="Buscar app...", id="apps-search")
            yield Select(
                [("Todas", "all"), ("Bloqueadas", "blocked"), ("Desbloqueadas", "unblocked")]
                + [(t, t) for t in APP_TYPES],
                id="apps-filter",
                value="all",
                prompt="Filtrar"
            )
            yield Select(
                [("Nombre (A-Z)", "name-asc"), ("Nombre (Z-A)", "name-desc")],
                id="apps-sort",
                value="name-asc",
                prompt="Ordenar"
            )
            yield Button("Registrar", id="apps-register", variant="primary")
            yield Select(
                [("Bloquear todo", "block-all"), ("Desbloquear todo", "unblock-all")],
                id="apps-acciones",
                prompt="Acciones rápidas",
            )

        yield Vertical(id="apps-container")

        with Horizontal(id="apps-footer"):
            yield Label("", id="apps-count", classes="apps-count")
            yield ClickableLabel("Cargar más", id="apps-more", classes="apps-more")

    def _schedule_apply(self):
        self._apply_seq += 1
        seq = self._apply_seq
        self.set_timer(1.5, lambda: self._do_apply(seq))

    def _do_apply(self, seq):
        if seq != self._apply_seq:
            return
        self.run_worker(apply_changes, name="apply-changes", group="firewall", thread=True)

    def ensure_loaded(self):
        """Carga la lista solo cuando el usuario abre la pestaña Apps.

        Evita pagar el coste de pintar todas las apps al arrancar la app,
        porque todas las vistas se montan aunque no se vean.
        """
        if self._loaded:
            return
        # Si se pide la carga mientras el panel todavía se está montando,
        # se difiere un ciclo: así los controles de la barra ya existen.
        if not self.query("#apps-count"):
            self.call_after_refresh(self.ensure_loaded)
            return
        self.refresh_apps()

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "apps-search":
            # Cada tecla reconstruía toda la lista: se espera a que pare.
            self._search_seq += 1
            seq = self._search_seq
            self.set_timer(BUSQUEDA_DELAY, lambda: self._do_search(seq))

    def _do_search(self, seq):
        if seq != self._search_seq:
            return
        self._pagina = PAGINADO_FILAS
        self.refresh_apps()

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "apps-acciones":
            value = event.value
            if value == "block-all":
                self.block_all()
            elif value == "unblock-all":
                self.unblock_all()
            event.select.clear()
        elif event.select.id in ("apps-filter", "apps-sort"):
            # Al montarse los Select disparan Changed; si la lista todavía no
            # se pintó se ignora (evita el coste al arrancar la app).
            if self._loaded:
                self._pagina = PAGINADO_FILAS
                self.refresh_apps()

    def on_button_pressed(self, event: Button.Pressed):
        btn_id = event.button.id
        if btn_id == "apps-register":
            self.register_app()
        elif btn_id and (btn_id.startswith("app-modify-") or btn_id.startswith("app-delete-")):
            node = event.button
            while node is not None:
                if isinstance(node, AppRow):
                    app_name = node.app_name
                    break
                node = node.parent
            else:
                return

            if btn_id.startswith("app-modify-"):
                self.modify_app(app_name)
            else:
                self.delete_app(app_name)

    def on_clickable_label_pressed(self, event: ClickableLabel.Pressed):
        """El pie de la lista usa un label clickeable en vez de un botón."""
        if event.label.id == "apps-more":
            self.load_more()

    def on_switch_changed(self, event: Switch.Changed):
        switch_id = event.switch.id
        if switch_id and switch_id.startswith("app-switch-"):
            node = event.switch
            while node is not None:
                if isinstance(node, AppRow):
                    app_name = node.app_name
                    break
                node = node.parent
            else:
                return

            data = self.load_apps()
            app_data = data.get(app_name)
            if not app_data:
                return

            blocked = event.value
            app_data["blocked"] = blocked
            self.save_apps(data)
            # Solo cambió una fila: no se reconstruye la lista completa.
            self._refresh_row(app_name)

            domains = app_data.get("domains", [])

            def _toggle():
                if blocked:
                    write_block_domains(domains)
                else:
                    remove_block_domains(domains)
                self.app.call_from_thread(self._schedule_apply)
                self.app.call_from_thread(
                    self.notify,
                    f"App '{app_name}' {'bloqueada' if blocked else 'desbloqueada'}"
                )

            self.run_worker(_toggle, name=f"block-{app_name}", group="firewall", thread=True)

    def load_apps(self) -> dict:
        if not os.path.exists(APPS_FILE):
            return {}
        try:
            with open(APPS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return {}

    def save_apps(self, data: dict):
        with open(APPS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def _filtered_names(self):
        data = self.load_apps()
        search = self.query_one("#apps-search", Input).value.lower()
        filter_opt = self.query_one("#apps-filter", Select).value
        sort_opt = self.query_one("#apps-sort", Select).value

        items = list(data.items())

        if search:
            items = [
                (n, d) for n, d in items
                if search in n.lower()
                or any(search in dom.lower() for dom in d.get("domains", []))
            ]

        if filter_opt == "blocked":
            items = [(n, d) for n, d in items if d.get("blocked")]
        elif filter_opt == "unblocked":
            items = [(n, d) for n, d in items if not d.get("blocked")]
        elif filter_opt != "all":
            items = [(n, d) for n, d in items if d.get("type", "Videojuegos") == filter_opt]

        reverse = False
        if sort_opt == "name-desc":
            reverse = True
        items.sort(key=lambda x: x[0].lower(), reverse=reverse)

        return items

    def refresh_apps(self):
        """Reconstruye la lista mostrando solo las primeras `_pagina` apps.

        Importante: las filas se montan en una sola llamada (`mount(*filas)`).
        Montarlas de a una obliga a Textual a recalcular el layout en cada
        montaje y multiplica el coste por el número de apps.
        """
        self._loaded = True

        container = self.query_one("#apps-container", Vertical)
        items = self._filtered_names()

        filas = [AppRow(nombre, info) for nombre, info in items[:self._pagina]]

        container.remove_children()
        if filas:
            container.mount(*filas)

        self._update_footer(len(filas), len(items))

    def load_more(self):
        """Agrega el siguiente tramo de apps sin volver a pintar las que ya están."""
        container = self.query_one("#apps-container", Vertical)
        items = self._filtered_names()

        nuevas = items[self._pagina:self._pagina + PAGINADO_FILAS]
        if not nuevas:
            return

        self._pagina += len(nuevas)
        container.mount(*[AppRow(nombre, info) for nombre, info in nuevas])

        self._update_footer(min(self._pagina, len(items)), len(items))

    def _update_footer(self, mostradas: int, total: int):
        count = self.query_one("#apps-count", Label)
        more = self.query_one("#apps-more", ClickableLabel)

        if total:
            count.update(f"Mostrando {mostradas} de {total} apps")
        else:
            count.update("Sin apps para mostrar")

        faltan = total - mostradas
        if faltan > 0:
            more.display = True
            more.update(f"▸ Cargar más ({faltan})")
        else:
            more.display = False

    def _refresh_row(self, app_name: str):
        """Actualiza una sola fila en sitio, sin tocar el resto de la lista.

        Alternar un Switch no necesita repintar la lista entera: alcanza con
        cambiar el estado de esa fila (barra de acento y etiqueta).
        """
        container = self.query_one("#apps-container", Vertical)

        fila = next(
            (
                child
                for child in container.children
                if getattr(child, "app_name", None) == app_name
            ),
            None,
        )
        if fila is None:
            return

        info = self.load_apps().get(app_name)
        if not info:
            return

        fila.update_state(info.get("blocked", False))

    def modify_app(self, app_name: str):
        data = self.load_apps()
        app_data = data.get(app_name)
        if not app_data:
            self.notify(f"App '{app_name}' no encontrada", severity="error")
            return

        def on_save(result):
            if not result:
                return
            data = self.load_apps()
            old_blocked = data[app_name].get("blocked", False)
            old_domains = data[app_name].get("domains", [])
            new_blocked = result["blocked"]
            new_domains = result["domains"]
            new_name = result["name"]

            data.pop(app_name, None)
            data[new_name] = {
                "type": result.get("type", "Videojuegos"),
                "domains": new_domains,
                "blocked": new_blocked,
            }
            self.save_apps(data)
            self.refresh_apps()

            def _apply():
                if new_blocked:
                    if old_blocked and set(old_domains) != set(new_domains):
                        remove_block_domains(old_domains)
                    write_block_domains(new_domains)
                elif old_blocked:
                    remove_block_domains(old_domains)
                self.app.call_from_thread(self._schedule_apply)
                self.app.call_from_thread(self.notify, f"App '{new_name}' modificada")

            self.run_worker(_apply, name=f"modify-{app_name}", group="firewall", thread=True)

        existing = set(self.load_apps().keys())
        self.app.push_screen(
            AppModal(app_data={"name": app_name, **app_data}, existing_names=existing),
            on_save
        )

    def delete_app(self, app_name: str):
        data = self.load_apps()
        app_data = data.get(app_name)
        if not app_data:
            self.notify(f"App '{app_name}' no encontrada", severity="error")
            return

        def on_confirm(confirmed):
            if not confirmed:
                return
            data = self.load_apps()
            app_data = data.pop(app_name, None)
            self.save_apps(data)
            self.refresh_apps()

            def _unblock():
                if app_data and app_data.get("blocked"):
                    remove_block_domains(app_data.get("domains", []))
                self.app.call_from_thread(self._schedule_apply)
                self.app.call_from_thread(self.notify, f"App '{app_name}' eliminada")

            self.run_worker(_unblock, name=f"delete-{app_name}", group="firewall", thread=True)

        self.app.push_screen(
            ConfirmScreen(f"Eliminar app '{app_name}'?"),
            on_confirm
        )

    def register_app(self):
        def on_save(result):
            if not result:
                return
            data = self.load_apps()
            data[result["name"]] = {
                "type": result.get("type", "Videojuegos"),
                "domains": result["domains"],
                "blocked": result["blocked"],
            }
            self.save_apps(data)
            self.refresh_apps()

            def _block():
                if result["blocked"]:
                    write_block_domains(result["domains"])
                self.app.call_from_thread(self._schedule_apply)
                self.app.call_from_thread(self.notify, f"App '{result['name']}' registrada")

            self.run_worker(_block, name=f"register-{result['name']}", group="firewall", thread=True)

        existing = set(self.load_apps().keys())
        self.app.push_screen(AppModal(existing_names=existing), on_save)

    def block_all(self):
        data = self.load_apps()
        if not data:
            self.notify("No hay apps registradas", severity="warning")
            return

        visible = self._filtered_names()
        if not visible:
            self.notify("No hay apps en el filtro actual", severity="warning")
            return

        if len(visible) == len(data):
            msg = f"¿Bloquear todas las apps ({len(visible)})?"
        else:
            msg = f"¿Bloquear las {len(visible)} apps del filtro actual?"

        self.app.push_screen(
            ConfirmScreen(msg, confirm_text="Bloquear"),
            self._do_block_all
        )

    def _do_block_all(self, confirmed):
        if not confirmed:
            return
        data = self.load_apps()
        visible = [name for name, _ in self._filtered_names()]
        if not visible:
            self.notify("No hay apps en el filtro actual", severity="warning")
            return

        all_domains = []
        for name in visible:
            info = data[name]
            info["blocked"] = True
            all_domains.extend(info.get("domains", []))
        self.save_apps(data)
        self.refresh_apps()

        def _work():
            write_block_domains(all_domains)
            self.app.call_from_thread(self._schedule_apply)
            self.app.call_from_thread(
                self.notify,
                f"{len(visible)} apps bloqueadas"
            )

        self.run_worker(_work, name="block-all", group="firewall", thread=True)

    def unblock_all(self):
        data = self.load_apps()
        if not data:
            self.notify("No hay apps registradas", severity="warning")
            return

        visible = self._filtered_names()
        if not visible:
            self.notify("No hay apps en el filtro actual", severity="warning")
            return

        if len(visible) == len(data):
            msg = f"¿Desbloquear todas las apps ({len(visible)})?"
        else:
            msg = f"¿Desbloquear las {len(visible)} apps del filtro actual?"

        self.app.push_screen(
            ConfirmScreen(msg, confirm_text="Desbloquear"),
            self._do_unblock_all
        )

    def _do_unblock_all(self, confirmed):
        if not confirmed:
            return
        data = self.load_apps()
        visible = [name for name, _ in self._filtered_names()]
        if not visible:
            self.notify("No hay apps en el filtro actual", severity="warning")
            return

        for name in visible:
            data[name]["blocked"] = False
        self.save_apps(data)
        self.refresh_apps()

        def _work():
            from firewall_ops import get_dns_block_file
            dns_conf = get_dns_block_file()
            if os.path.exists(dns_conf):
                os.remove(dns_conf)
            self.app.call_from_thread(self._schedule_apply)
            self.app.call_from_thread(
                self.notify,
                f"{len(visible)} apps desbloqueadas"
            )

        self.run_worker(_work, name="unblock-all", group="firewall", thread=True)
