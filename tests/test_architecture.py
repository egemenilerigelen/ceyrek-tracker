"""Katman kuralları: bağımlılık yalnızca aşağıya doğru olabilir.

    app  ->  cards/<özellik>  ->  core  ->  infra, theme

- `theme` ve `infra` hiçbir üst katmanı bilmez.
- `core` (panel iskeleti) hiçbir karta ve `app`'e bağımlı olmaz; kartlar çekirdeğe yalnızca
  `CardSpec` aracılığıyla takılır.
- Her kart özelliği (`cards/weather`, `cards/finance`...) yalnızca kendi paketini, `core`,
  `infra` ve `theme`'i kullanır; kartlar birbirini bilmez.
- `core/platform` (Windows'a özgü kod) yalnızca kendi paketini kullanır.
- Yalnızca `app` (birleştirme noktası) her şeyi bilebilir; kimse `app`'i import etmez.

Yeni bir bağımlılık bu kurallara aykırıysa test düşer; kuralı gevşetmek yerine bağımlılığı
doğru katmana taşımak gerekir.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
ROOT = "ceyrek_tracker"


def _modules():
    for path in sorted((SRC / ROOT).rglob("*.py")):
        parts = list(path.relative_to(SRC).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        yield ".".join(parts), path


def _imports(path, known):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    resolved = set()
    for name in found:
        # `from paket import isim`: isim modül değil nitelikse (ör. APP_NAME) pakete indirgenir.
        while name not in known and "." in name:
            name = name.rsplit(".", 1)[0]
        if name == ROOT or name.startswith(ROOT + "."):
            resolved.add(name)
    return resolved


def _layer(module):
    """Modülün katmanı: theme, infra, core, core.platform, cards, cards.<özellik>, app."""
    parts = module.split(".")[1:]
    if not parts:
        return "root"
    if parts[0] == "cards":
        return "cards" if len(parts) == 1 else f"cards.{parts[1]}"
    if parts[0] == "core" and len(parts) > 1 and parts[1] == "platform":
        return "core.platform"
    return parts[0]


def _allowed(layer, target_layer):
    if target_layer in ("root", layer):
        return True  # paket sabitleri (APP_NAME...) ve kendi katmanı
    if layer in ("theme", "infra", "core.platform"):
        return False
    if layer == "core":
        return target_layer in ("theme", "infra", "core.platform")
    if layer == "cards":  # kart kayıt defteri: özellikleri toplar
        return target_layer.startswith("cards.") or target_layer in ("core", "core.platform")
    if layer.startswith("cards."):  # tek bir kart özelliği
        return target_layer in ("core", "theme", "infra")
    return layer in ("app", "__main__")


KNOWN = {module for module, _ in _modules()}
VIOLATIONS = []
for module, path in _modules():
    for target in _imports(path, KNOWN):
        if not _allowed(_layer(module), _layer(target)):
            VIOLATIONS.append(f"{module} -> {target}")


def test_layering_rules_hold():
    assert not VIOLATIONS, "Katman kuralı ihlalleri:\n  " + "\n  ".join(VIOLATIONS)


@pytest.mark.parametrize(
    ("module", "layer"),
    [
        ("ceyrek_tracker.core.panel_window", "core"),
        ("ceyrek_tracker.core.platform.hotkey", "core.platform"),
        ("ceyrek_tracker.cards.weather.card", "cards.weather"),
        ("ceyrek_tracker.cards", "cards"),
        ("ceyrek_tracker.infra.http", "infra"),
    ],
)
def test_layer_detection(module, layer):
    assert _layer(module) == layer


def test_rules_reject_forbidden_directions():
    assert not _allowed("core", "cards.weather")
    assert not _allowed("cards.weather", "cards.finance")
    assert not _allowed("cards.weather", "app")
    assert not _allowed("infra", "core")
    assert not _allowed("theme", "infra")
    assert _allowed("cards.weather", "core")
    assert _allowed("app", "cards.weather")
