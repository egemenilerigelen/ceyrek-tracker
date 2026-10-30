"""Panelin arkasındaki masaüstünün bulanık bir kopyası (cam efekti).

Windows 10'un yerleşik acrylic efekti pencere bölgesini (region) yok sayıp pencerenin tüm
dikdörtgenini boyar; yuvarlak köşeler bu yüzden kesilemiyor. Bu yüzden panel açılırken
arkasındaki ekran görüntüsü alınıp bulanıklaştırılır ve panel yüzeyi bunu kendisi, antialiased
yuvarlak köşeyle çizer. Görüntü panel açıkken yenilenmez; üstüne %80 civarı koyu bir tabaka
bindiği için eskimesi fark edilmez. Panel arkadaki pencereleri canlı göstermediğinden alttaki
düğmelerin hayaleti de görünmez.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPixmap, QScreen

# Kaç kez yarıya küçültüleceği: arttıkça daha bulanık (ve daha ucuz) olur.
BLUR_STEPS = 5


def blur_image(image: QImage, steps: int = BLUR_STEPS) -> QImage:
    """Art arda yarıya küçültüp (her adım 2x2 komşuluğu ortalar) yumuşak büyüterek bulanıklaştırır.

    Tek adımda büyük oranda küçültmek örnekleme yaptığı için çizgili/ince desenleri
    bulanıklaştırmaz; adım adım küçültmek gerçek bir ortalama verir.
    """
    width, height = image.width(), image.height()
    small = image
    for _ in range(steps):
        if small.width() < 4 or small.height() < 4:
            break
        small = small.scaled(
            small.width() // 2,
            small.height() // 2,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return small.scaled(
        width,
        height,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def capture_blurred(screen: QScreen, rect: QRect) -> QPixmap | None:
    """`rect` (ekran koordinatı, mantıksal px) bölgesinin bulanık görüntüsü; alınamazsa None."""
    full = screen.grabWindow(0)
    if full.isNull():
        return None
    ratio = full.devicePixelRatio() or 1.0
    origin = screen.geometry().topLeft()
    source = QRect(
        round((rect.x() - origin.x()) * ratio),
        round((rect.y() - origin.y()) * ratio),
        round(rect.width() * ratio),
        round(rect.height() * ratio),
    ).intersected(full.rect())
    if source.isEmpty():
        return None
    result = QPixmap.fromImage(blur_image(full.copy(source).toImage()))
    result.setDevicePixelRatio(ratio)
    return result
