"""Ağ gecikmesi: bir sunucuya TCP bağlantısı kurma süresi.

ICMP ping yönetici yetkisi ya da dış süreç ister; TCP el sıkışması aynı bilgiyi (gidiş-dönüş
süresi) yetkisiz verir. Sistem örneklemesinden ayrı çalışır: yanıt gelmezse zaman aşımı
(1 sn) diğer değerlerin güncellenmesini geciktirmesin.
"""

from __future__ import annotations

import socket
import time

PING_HOST = "1.1.1.1"
PING_PORT = 443
PING_TIMEOUT = 1.0


def tcp_ping(
    host: str = PING_HOST, port: int = PING_PORT, timeout: float = PING_TIMEOUT
) -> float | None:
    """Bağlantı süresi (ms); sunucuya ulaşılamıyorsa None."""
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError:
        return None
    return (time.perf_counter() - started) * 1000
