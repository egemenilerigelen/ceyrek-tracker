from ceyrek_tracker.cards.clipboard.history import (
    MAX_ITEMS,
    PREVIEW_CHARS,
    ClipboardHistory,
    preview,
)


def test_newest_comes_first():
    history = ClipboardHistory()
    for text in ("bir", "iki", "üç"):
        assert history.add(text)
    assert history.items == ("üç", "iki", "bir")


def test_keeps_only_the_last_five():
    history = ClipboardHistory()
    for number in range(MAX_ITEMS + 3):
        history.add(f"metin {number}")
    assert len(history.items) == MAX_ITEMS == 5
    assert history.items[0] == "metin 7"
    assert history.items[-1] == "metin 3"


def test_repeating_the_top_item_changes_nothing():
    history = ClipboardHistory()
    history.add("a")
    assert not history.add("a")
    assert history.items == ("a",)


def test_repeating_an_older_item_moves_it_to_the_top_without_duplicating():
    history = ClipboardHistory()
    for text in ("a", "b", "c"):
        history.add(text)
    assert history.add("a")
    assert history.items == ("a", "c", "b")


def test_blank_text_is_ignored():
    history = ClipboardHistory()
    assert not history.add("")
    assert not history.add(" \n\t ")
    assert history.items == ()


def test_text_is_stored_exactly_as_copied():
    history = ClipboardHistory()
    history.add("  satır 1\nsatır 2  ")
    assert history.items == ("  satır 1\nsatır 2  ",)


def test_preview_flattens_whitespace():
    assert preview("  def f():\n\treturn 1\n") == "def f(): return 1"


def test_preview_cuts_very_long_text():
    shown = preview("x" * (PREVIEW_CHARS * 5))
    assert shown == "x" * PREVIEW_CHARS + "…"
    assert preview("kısa") == "kısa"


def test_remove_drops_only_that_text():
    history = ClipboardHistory()
    for text in ("a", "b", "c"):
        history.add(text)
    assert history.remove("b")
    assert history.items == ("c", "a")
    assert not history.remove("b")
    assert history.add("b")  # silinen metin yeniden kopyalanınca geri gelir
