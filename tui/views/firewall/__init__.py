from textual.containers import Vertical, Horizontal
from textual.widgets import Label, Button, ContentSwitcher

from views.firewall.rules import RulesTab
from views.firewall.apps import AppsTab


class FirewallView(Vertical):
    def compose(self):
        with Horizontal(classes="fw-tab-bar"):
            yield Button("Reglas", id="fw-tab-rules", classes="fw-tab active")
            yield Button("Apps", id="fw-tab-apps", classes="fw-tab")

        with ContentSwitcher(initial="fw-panel-rules", id="fw-content"):
            yield RulesTab(id="fw-panel-rules")
            yield AppsTab(id="fw-panel-apps")

    def on_button_pressed(self, event: Button.Pressed):
        mapping = {
            "fw-tab-rules": "fw-panel-rules",
            "fw-tab-apps": "fw-panel-apps",
        }
        panel_id = mapping.get(event.button.id)
        if panel_id:
            self.query_one("#fw-content", ContentSwitcher).current = panel_id
            for btn in self.query(".fw-tab"):
                btn.remove_class("active")
            event.button.add_class("active")
