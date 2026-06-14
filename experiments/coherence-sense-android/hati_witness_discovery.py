#!/usr/bin/env python3
"""Advertise the Mac witness as a local Hati service without requiring typed IPs."""

from __future__ import annotations

import atexit
import socket
import subprocess
from dataclasses import dataclass

SERVICE_TYPE = "_hati-witness._tcp"
SERVICE_NAME = "Hati Mac Witness"


@dataclass
class MdnsAdvertisement:
    process: subprocess.Popen | None
    reason: str

    @property
    def active(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self) -> None:
        if not self.active or self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()


def lan_ipv4_addresses() -> list[str]:
    """Return likely LAN IPv4 addresses for humans and fallback clients."""
    found: list[str] = []
    for iface in ("en0", "en1", "en2", "bridge100"):
        try:
            out = subprocess.run(
                ["ipconfig", "getifaddr", iface],
                capture_output=True,
                text=True,
                timeout=1,
            )
        except Exception:
            continue
        ip = out.stdout.strip()
        if ip and ip not in found:
            found.append(ip)
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in found:
                found.append(ip)
    except Exception:
        pass
    return found


def witness_descriptor(port: int, mode: str) -> dict[str, object]:
    urls = [f"http://{ip}:{port}" for ip in lan_ipv4_addresses()]
    return {
        "mesh": "hati.mesh",
        "service_name": SERVICE_NAME,
        "service_type": SERVICE_TYPE,
        "mode": mode,
        "port": port,
        "sense_path": "/sense",
        "state_path": "/state",
        "urls": urls,
        "floor": "LAN mDNS advertises the witness; HTTP descriptor and dashboard show fallback URLs.",
        "north_star": "organs negotiate local channels by signed heartbeat and select the highest-fidelity carrier without typed configuration.",
    }


def start_mdns_advertisement(port: int, mode: str) -> MdnsAdvertisement:
    """Register the witness with macOS dns-sd when that native tool is available."""
    if subprocess.run(["/usr/bin/which", "dns-sd"], capture_output=True, text=True).returncode != 0:
        return MdnsAdvertisement(None, "dns-sd unavailable")
    txt = [
        "mesh=hati.mesh",
        f"mode={mode}",
        "path=/sense",
        "state=/state",
        "codec=json",
        "floor=mdns-http",
    ]
    try:
        proc = subprocess.Popen(
            ["dns-sd", "-R", SERVICE_NAME, SERVICE_TYPE, "local", str(port), *txt],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        return MdnsAdvertisement(None, str(exc))
    adv = MdnsAdvertisement(proc, "advertising")
    atexit.register(adv.stop)
    return adv
