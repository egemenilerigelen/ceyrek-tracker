"""Kart arayüzü.

Yeni kart eklemek: `cards/` altına bir dosya aç, `Card`'ı türet, dosyanın sonunda bir
`CardSpec` tanımla ve `cards/__init__.py` içindeki `CARDS` listesine ekle.

- Kart panel kapalıyken de yaşar ama ağır işini `on_show()` / `on_hide()` ile açıp
  kapatmalıdır (zamanlayıcılar, animasyonlar yalnızca panel açıkken çalışmalı).
- Hata yönetimi: kart `error_changed` sinyaliyle anlaşılır bir mesaj yayınlar;
  `CardHost` bunu yalnızca o kartın içinde gösterir, panel etkilenmez.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QWidget

from ceyrek_tracker.theme import Look

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CardContext:
    look: Look
    config: dict[str, Any] = field(default_factory=dict)


class Card(QWidget):
    info_changed = Signal(str)  # başlık satırının sağında gösterilen kısa bilgi
    error_changed = Signal(str)  # boş metin = hata yok
    config_changed = Signal(object)  # kullanıcı kartın ayarını değiştirdi; kalıcı saklanmalı

    def __init__(self, context: CardContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.look = context.look
        self.config = context.config
        # Kart, çerçevesine (CardHost) bağlanmadan önce de bilgi/hata üretebilir; son değerler
        # saklanır ve çerçeve kurulurken okunur.
        self.current_info = ""
        self.current_error = ""
        # Varsa başlık satırındaki bilgiye tıklanınca açılır (ör. hava kartında konum seçimi).
        self.info_menu: QMenu | None = None

    def on_show(self) -> None:
        """Panel açıldı: zamanlayıcıları başlat, veriyi tazele."""

    def on_hide(self) -> None:
        """Panel kapandı: zamanlayıcıları ve animasyonları durdur."""

    def set_look(self, look: Look) -> None:
        self.look = look
        self.update()

    def shutdown(self) -> None:
        """Uygulama kapanırken arka plan işlerini durdur."""

    def save_config(self, key: str, value: Any) -> None:
        self.config[key] = value
        self.config_changed.emit(dict(self.config))

    def set_info(self, text: str) -> None:
        self.current_info = text
        self.info_changed.emit(text)

    def fail(self, message: str) -> None:
        self.current_error = message
        self.error_changed.emit(message)

    def clear_error(self) -> None:
        self.fail("")


def guarded(method: Callable[..., Any]) -> Callable[..., Any]:
    """Kart metodunu sarar: beklenmedik bir istisna paneli çökertmez, kartta görünür."""

    @wraps(method)
    def wrapper(self: Card, *args: Any, **kwargs: Any) -> Any:
        try:
            return method(self, *args, **kwargs)
        except Exception:
            logger.exception("%s.%s içinde beklenmedik hata", type(self).__name__, method.__name__)
            self.fail("Bu kart beklenmedik bir hata verdi. Ayrıntılar log dosyasında.")
            return None

    return wrapper


@dataclass(frozen=True)
class CardSpec:
    id: str
    title: str
    icon: str  # Segoe MDL2 Assets karakteri
    factory: Callable[[CardContext], Card]
    default_enabled: bool = True
