from ceyrek_tracker.core.widgets import ElidedLabel


def test_elided_label_shortens_long_text_and_keeps_full_text(qtbot):
    label = ElidedLabel("value")
    qtbot.addWidget(label)
    label.show()
    label.resize(60, 20)
    label.set_full_text("Çok uzun bir şarkı adı: Bir Varmış Bir Yokmuş")
    assert label.text().endswith("…")
    assert label.full_text().startswith("Çok uzun")
    assert label.toolTip() == label.full_text()
    label.resize(600, 20)
    assert label.text() == label.full_text()
    assert label.toolTip() == ""
