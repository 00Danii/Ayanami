from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, ContentSwitcher

from views.firewall.rules import RulesTab
from views.firewall.apps import AppsTab
from views.firewall.config import ConfigTab


class FirewallView(Vertical):
    def compose(self):
        with Horizontal(classes="fw-tab-bar"):
            yield Button("Apps", id="fw-tab-apps", classes="fw-tab active")
            yield Button("Reglas", id="fw-tab-rules", classes="fw-tab")
            yield Button("Config", id="fw-tab-config", classes="fw-tab")

        with ContentSwitcher(initial="fw-panel-apps", id="fw-content"):
            yield AppsTab(id="fw-panel-apps")
            yield RulesTab(id="fw-panel-rules")
            yield ConfigTab(id="fw-panel-config")

    def on_button_pressed(self, event: Button.Pressed):
        mapping = {
            "fw-tab-rules": "fw-panel-rules",
            "fw-tab-apps": "fw-panel-apps",
            "fw-tab-config": "fw-panel-config",
        }
        panel_id = mapping.get(event.button.id)
        if panel_id:
            self.query_one("#fw-content", ContentSwitcher).current = panel_id
            for btn in self.query(".fw-tab"):
                btn.remove_class("active")
            event.button.add_class("active")
