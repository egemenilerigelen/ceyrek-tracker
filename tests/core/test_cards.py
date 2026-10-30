import pytest
from PySide6.QtWidgets import QLabel, QVBoxLayout

from ceyrek_tracker.core.card_base import Card, CardContext, CardSpec, guarded
from ceyrek_tracker.core.card_manager import CardManager, reconcile
from ceyrek_tracker.core.settings import CardSetting
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)


class _Plain(Card):
    def __init__(self, context):
        super().__init__(context)
        self.shown = 0
        self.hidden = 0

    def on_show(self):
        self.shown += 1

    def on_hide(self):
        self.hidden += 1


class _Exploding(Card):
    def on_show(self):
        raise RuntimeError("kart bozuldu")

    @guarded
    def slot(self):
        raise ValueError("slot bozuldu")


def _spec(card_id, factory, default_enabled=True):
    return CardSpec(card_id, card_id.title(), "", factory, default_enabled)


def test_reconcile_keeps_saved_order_drops_unknown_and_appends_new():
    specs = [_spec("a", _Plain), _spec("b", _Plain), _spec("c", _Plain, default_enabled=False)]
    saved = [CardSetting("b", collapsed=True), CardSetting("gone"), CardSetting("a", enabled=False)]
    result = reconcile(specs, saved)
    assert [(c.id, c.enabled, c.collapsed) for c in result] == [
        ("b", True, True),
        ("a", False, False),
        ("c", False, False),
    ]


def test_disabled_cards_are_not_built(qtbot):
    built = []

    def factory(context):
        built.append(1)
        return _Plain(context)

    manager = CardManager([_spec("a", factory)], [CardSetting("a", enabled=False)], LOOK)
    assert manager.hosts == []
    assert built == []


def test_factory_failure_is_isolated_to_its_card(qtbot):
    def broken(context):
        raise RuntimeError("kurulamadı")

    manager = CardManager([_spec("bad", broken), _spec("ok", _Plain)], [], LOOK)
    assert [h.spec.id for h in manager.hosts] == ["bad", "ok"]
    assert manager.hosts[0].card is None
    assert "başlatılamadı" in manager.hosts[0]._error.text()
    manager.show_all()  # kartı olmayan çerçeve de sorunsuz yönetilir
    manager.hide_all()
    assert manager.hosts[1].card.shown == 1
    assert manager.hosts[1].card.hidden == 1


def test_lifecycle_exception_shows_error_in_card_only(qtbot):
    manager = CardManager([_spec("x", _Exploding), _spec("ok", _Plain)], [], LOOK)
    manager.show_all()
    assert not manager.hosts[0]._error.isHidden()
    assert manager.hosts[1]._error.isHidden()
    assert manager.hosts[1].card.shown == 1


def test_guarded_slot_reports_error_instead_of_raising(qtbot):
    card = _Exploding(CardContext(LOOK))
    errors = []
    card.error_changed.connect(errors.append)
    card.slot()
    assert errors and "beklenmedik" in errors[0]


def test_info_and_error_set_before_host_exists_are_shown(qtbot):
    def factory(context):
        card = _Plain(context)
        card.set_info("İstanbul")
        card.fail("kurulumda hata")
        return card

    host = CardManager([_spec("a", factory)], [], LOOK).hosts[0]
    assert host._info.text() == "İstanbul"
    assert host._error.text() == "kurulumda hata"


def test_collapse_toggles_state_and_notifies(qtbot):
    manager = CardManager([_spec("a", _Plain)], [], LOOK, animate=False)
    host = manager.hosts[0]
    with qtbot.waitSignal(manager.collapsed_changed) as blocker:
        host.toggle()
    assert blocker.args == ["a", True]
    assert host.collapsed
    assert host._body.isHidden()
    host.toggle()
    assert not host.collapsed
    assert not host._body.isHidden()


def test_saved_collapsed_state_is_restored(qtbot):
    manager = CardManager([_spec("a", _Plain)], [CardSetting("a", collapsed=True)], LOOK)
    assert manager.hosts[0].collapsed
    manager.set_collapsed("a", False)
    assert not manager.card_settings()[0].collapsed


@pytest.mark.parametrize("animate", [True, False])
def test_collapse_while_visible_ends_in_final_state(qtbot, animate):
    manager = CardManager([_spec("a", _Plain)], [], LOOK, animate=animate)
    host = manager.hosts[0]
    qtbot.addWidget(host)
    host.show()
    host.toggle()
    qtbot.waitUntil(lambda: host._body.isHidden(), timeout=2000)


def test_card_config_change_is_persisted_through_manager(qtbot):
    manager = CardManager([_spec("a", _Plain)], [CardSetting("a", config={"x": 1})], LOOK)
    changes = []
    manager.config_changed.connect(lambda card_id, config: changes.append((card_id, config)))
    manager.hosts[0].card.save_config("city", "Urla")
    assert changes == [("a", {"x": 1, "city": "Urla"})]
    manager.set_config(*changes[0])
    assert manager.card_settings()[0].config == {"x": 1, "city": "Urla"}


class _Tall(Card):
    """Katlanma animasyonunu gözle görülür kılacak kadar uzun bir kart."""

    def __init__(self, context):
        super().__init__(context)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("x"))
        self.setMinimumHeight(200)


def test_reversing_collapse_mid_animation_continues_from_current_height(qtbot):
    # Art arda tıklayınca kart sıfırdan başlayıp zıplamamalı.
    manager = CardManager([_spec("a", _Tall)], [], LOOK, animate=True)
    host = manager.hosts[0]
    qtbot.addWidget(host)
    host.show()
    host.set_collapsed(True)
    qtbot.wait(80)  # animasyonun ortası
    mid = host._body.height()
    assert 0 < mid < 200
    host.set_collapsed(False)  # yön değişti
    assert host._anim.startValue() == mid
    assert host._body.maximumHeight() == mid


def test_zero_height_body_leaves_no_gap_below_the_header(qtbot):
    # Animasyonun başında/sonunda gövde görünür ama yüksekliği 0'dır; aradaki boşluk
    # o anda bir anda belirip kaybolarak kartı zıplatmamalı.
    manager = CardManager([_spec("a", _Tall)], [], LOOK, animate=False)
    host = manager.hosts[0]
    qtbot.addWidget(host)
    host.show()
    host._body.setMaximumHeight(0)
    header_height = host.layout().itemAt(0).widget().sizeHint().height()
    assert host.sizeHint().height() == header_height
