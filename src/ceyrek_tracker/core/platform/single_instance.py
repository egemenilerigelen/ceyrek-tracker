"""Aynı anda tek kopya çalışsın diye kilit dosyası."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLockFile


def acquire_single_instance(lock_path: Path) -> QLockFile | None:
    """Kilidi alır; başka kopya varsa None döner.

    Kilidi tutan işlem artık çalışmıyorsa (çökme, görev yöneticisinden sonlandırma) Qt
    kilidi kendisi bayat sayıp temizler; uygulama çöktükten sonra da açılır. Süre bazlı
    bayatlama kapatılır: uygulama günlerce açık kalır ve Qt'nin varsayılan 30 sn'si
    sonrasında canlı bir kopyanın kilidi çalınabilirdi.
    """
    lock = QLockFile(str(lock_path))
    lock.setStaleLockTime(0)
    if lock.tryLock(100):
        return lock
    return None
