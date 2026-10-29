"""Supervisor centralizado de bloqueos VPN para AYANAMI (iptables IPv4).

Una sola lectura de FORWARD por ciclo. Una entrada por MAC en modo dispositivo,
con múltiples watchers de endpoints VPN.
"""
import re
import subprocess
import threading
import time


class VPNBlockSupervisor:
    def __init__(
        self,
        duration,
        log,
        interval=1.0,
        block_device=True,
        watch_duration=300,
    ):
        if duration <= 0 or interval <= 0:
            raise ValueError(
                "duration e interval deben ser positivos"
            )
        self.duration = float(duration)
        self.interval = float(interval)
        self.watch_duration = float(watch_duration)
        self.log = log
        self.block_device = block_device
        self.blocks = {}
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None


    @staticmethod
    def _run(*args):
        return subprocess.run(["iptables", "-w", "2", *args],
                              text=True, capture_output=True, check=False, timeout=10)

    def _add(self, rule):
        check = self._run("-C", "FORWARD", *rule)
        if check.returncode == 0:
            return False  # preexistente: no es nuestra, no se debe eliminar
        result = self._run("-I", "FORWARD", "1", *rule)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "No se pudo instalar regla")
        return True

    def _remove(self, rule):
        result = self._run("-D", "FORWARD", *rule)
        if result.returncode != 0:
            self.log(f"[VPN] Aviso: no se pudo retirar regla: {result.stderr.strip()}")

    def start(self):
        if self.block_device:
            result = self._run("-N", "AYANAMI_CNT")
            if result.returncode != 0:
                check = self._run("-L", "AYANAMI_CNT", "-n")
                if check.returncode != 0:
                    raise RuntimeError("No se pudo crear/verificar AYANAMI_CNT")
        self.thread = threading.Thread(target=self._loop, name="ayanami-vpn-supervisor", daemon=True)
        self.thread.start()

    def register(self, mac, client_ip, remote_ip, remote_port, transport):
        """Añade un endpoint VPN al bloqueo. Devuelve True si creó un bloqueo."""
        mac = mac.lower()
        transport = transport.lower()
        endpoint = (remote_ip, int(remote_port), transport)
        key = mac if self.block_device else (mac, endpoint)
        target = "AYANAMI_CNT" if self.block_device else "REJECT"
        flow_rule = ["-m", "mac", "--mac-source", mac, "-d", remote_ip,
                     "-p", transport, "--dport", str(remote_port), "-j", target]
        block_rule = (["-m", "mac", "--mac-source", mac, "-j", "DROP"]
                      if self.block_device else flow_rule)
        with self.lock:
            state = self.blocks.get(key)
            if state is not None and endpoint in state["flows"]:
                return False
            if state is None:
                # En modo dispositivo, DROP primero y watcher después (posición 1).
                owned_block = self._add(block_rule)
                if not owned_block:
                    self.log(f"[VPN] Regla preexistente para {mac}; no se asumirá su propiedad")
                    return False
                state = {
                    "mac": mac,
                    "ip": client_ip,
                    "block": block_rule,
                    "flows": {},
                    "last_activity": time.monotonic(),
                    "watch_started": None,
                    "status": "BLOCKED",
                }
                self.blocks[key] = state
                created = True
            else:
                created = False
            if self.block_device:
                try:
                    owned_flow = self._add(flow_rule)
                except Exception:
                    if created:
                        self._remove(block_rule)
                        self.blocks.pop(key, None)
                    raise
                if not owned_flow:
                    self.log(f"[VPN] Watcher preexistente para {mac} {endpoint}; no se añadirá")
                    if created:
                        self._remove(block_rule)
                        self.blocks.pop(key, None)
                    return False
            state["flows"][endpoint] = {"rule": flow_rule, "count": None,
                                          "owned": self.block_device}
            self.log(f"[VPN] {'Bloqueo instalado' if created else 'Nuevo flujo vigilado'}: "
                     f"MAC={mac} destino={remote_ip}:{remote_port}/{transport}")
            return created

    @staticmethod
    def _read_counters(stdout):
        """
        Extrae los contadores de iptables-save -c -t filter.
        Índice:
        (MAC, IP remota, protocolo, puerto, target)
        """
        import shlex
        import ipaddress

        counters = {}
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("["):
                continue
            try:
                counter, rule_text = line.split("] ", 1)
                packets = int(counter[1:].split(":")[0])
                parts = shlex.split(rule_text)
                if len(parts) < 4:
                    continue
                if parts[0] != "-A" or parts[1] != "FORWARD":
                    continue

                def get_option(option):
                    if option not in parts:
                        return None
                    idx = parts.index(option)
                    if idx + 1 < len(parts):
                        return parts[idx + 1]
                    return None

                target = get_option("-j")
                proto = get_option("-p")
                destination = get_option("-d")
                mac = get_option("--mac-source")
                port = get_option("--dport")

                if not target or not proto or not destination or not mac or not port:
                    continue
                if target not in ("AYANAMI_CNT", "REJECT", "DROP"):
                    # Solo nos interesan reglas vigiladas por el supervisor.
                    if target not in ("AYANAMI_CNT", "REJECT"):
                        continue

                # Normalizar IP: iptables-save puede usar 84.20.27.34/32
                if "/" in destination:
                    destination = destination.split("/", 1)[0]
                try:
                    destination = str(ipaddress.ip_address(destination))
                except ValueError:
                    pass

                key = (mac.lower(), destination, proto.lower(), int(port), target)
                counters[key] = counters.get(key, 0) + packets
            except (ValueError, IndexError):
                continue
        return counters

    def _tick(self):
        result = subprocess.run(
            ["iptables-save", "-c", "-t", "filter"],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            self.log(
                f"[VPN] Error consultando contadores; "
                f"se conservan bloqueos: {result.stderr.strip()}"
            )
            return

        counters = self._read_counters(result.stdout)
        now = time.monotonic()

        with self.lock:
            for key, state in list(self.blocks.items()):
                status = state.get("status", "BLOCKED")
                valid = False
                increased = False

                for (remote_ip, remote_port, transport), flow in state["flows"].items():
                    target = "AYANAMI_CNT" if self.block_device else "REJECT"
                    lookup = (
                        state["mac"],
                        remote_ip,
                        transport,
                        remote_port,
                        target,
                    )
                    current = counters.get(lookup)
                    if current is None:
                        continue  # Regla ausente: no interpretar como inactividad

                    valid = True
                    previous = flow["count"]

                    if previous is None:
                        # Primera lectura del contador.
                        if current > 0:
                            increased = True
                    elif current > previous:
                        # Se detectaron nuevos paquetes.
                        increased = True
                    elif current < previous:
                        # El contador se reinició.
                        # Conservamos el bloqueo por precaución.
                        increased = True

                    flow["count"] = current

                if not valid:
                    self.log(
                        f"[VPN] Sin contador válido para "
                        f"{state['mac']}; bloqueo conservado"
                    )
                    continue

                # --------------------------------
                # MODO BLOQUEO POR DISPOSITIVO
                # --------------------------------
                if self.block_device:
                    if status == "BLOCKED":
                        if increased:
                            state["last_activity"] = now
                        elif (
                            now - state["last_activity"]
                            >= self.duration
                        ):
                            self._enter_watching_locked(
                                key,
                                state,
                            )

                    elif status == "WATCHING":
                        if increased:
                            self._reactivate_block_locked(
                                key,
                                state,
                            )
                        elif (
                            state["watch_started"] is not None
                            and
                            now - state["watch_started"]
                            >= self.watch_duration
                        ):
                            self._unblock_locked(
                                key,
                                state,
                            )

                # --------------------------------
                # MODO BLOQUEO POR FLUJO
                # --------------------------------
                else:
                    if increased:
                        state["last_activity"] = now
                    elif (
                        now - state["last_activity"]
                        >= self.duration
                    ):
                        self._unblock_locked(
                            key,
                            state,
                        )

    def _enter_watching_locked(self, key, state):
        """
        Retira el bloqueo general del dispositivo,
        pero conserva los watchers VPN.
        """
        if state.get("status") != "BLOCKED":
            return

        self._remove(state["block"])
        state["status"] = "WATCHING"
        state["watch_started"] = time.monotonic()

        self.log(
            f"[VPN] MAC={state['mac']} desbloqueada "
            f"por inactividad. Vigilancia activa "
            f"durante {self.watch_duration:.0f}s."
        )

    def _reactivate_block_locked(self, key, state):
        """
        Reinstala el bloqueo cuando un dispositivo
        en vigilancia vuelve a generar tráfico VPN.
        """
        if state.get("status") != "WATCHING":
            return

        block_rule = state["block"]

        try:
            installed = self._add(block_rule)
            if not installed:
                self.log(
                    f"[VPN] Regla DROP ya existente "
                    f"para MAC={state['mac']}."
                )
                # No se asume propiedad de una regla ajena.
                return

            # Los watchers deben quedar antes del DROP.
            # Reinsertamos los watchers administrados
            # para garantizar su prioridad.
            for flow in state["flows"].values():
                if not flow["owned"]:
                    continue
                self._remove(flow["rule"])
                self._add(flow["rule"])

            state["status"] = "BLOCKED"
            state["watch_started"] = None
            state["last_activity"] = time.monotonic()

            self.log(
                f"[VPN] VPN reactivada: "
                f"MAC={state['mac']}. "
                f"Bloqueo reinstalado automáticamente."
            )
        except Exception as exc:
            self.log(
                f"[VPN] Error reactivando bloqueo "
                f"de {state['mac']}: {exc}"
            )

    def _unblock_locked(self, key, state):
        """
        Elimina definitivamente el dispositivo
        del supervisor y retira sus reglas.
        """
        for flow in state["flows"].values():
            if flow["owned"]:
                self._remove(flow["rule"])

        # Solo retirar DROP si sigue instalado
        # y pertenece a este supervisor.
        if state.get("status") == "BLOCKED":
            self._remove(state["block"])

        self.blocks.pop(key, None)

        self.log(
            f"[VPN] Vigilancia finalizada: "
            f"MAC={state['mac']}"
        )

    def _loop(self):
        while not self.stop_event.wait(self.interval):
            try:
                self._tick()
            except Exception as exc:
                self.log(f"[VPN] Error en supervisor (bloqueos conservados): {exc}")

    def stop(self):
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join()
        with self.lock:
            for key, state in list(self.blocks.items()):
                self._unblock_locked(
                    key,
                    state,
                )
        self.log(
            "[VPN] Supervisor detenido. "
            "Reglas temporales retiradas."
        )
