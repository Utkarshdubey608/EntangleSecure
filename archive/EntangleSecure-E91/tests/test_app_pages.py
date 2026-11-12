"""UI smoke tests (Streamlit AppTest): every page renders and the main actions work without exceptions."""

from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGES = ["overview", "laboratory", "protocol", "eavesdropping", "reports"]


def _open(page: str):
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    if page != "overview":
        at.switch_page(f"screens/{page}.py")
        at.run()
    assert not at.exception, at.exception
    return at


def _button(at, label: str):
    matches = [b for b in at.button if b.label == label]
    assert matches, f"button {label!r} not found; have {[b.label for b in at.button]}"
    return matches[0]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    _open(page)


def test_overview_actions():
    at = _open("overview")
    before = len(at.session_state.history)
    _button(at, "Toggle Eve and rerun").click().run()
    assert not at.exception
    assert at.session_state.result.config.eve.enabled
    assert len(at.session_state.history) == before + 1


def test_laboratory_run_and_reset():
    at = _open("laboratory")
    at.number_input(key="lab_n").set_value(3000)
    at.slider(key="lab_noise").set_value(0.05)
    at.button(key="FormSubmitter:lab_form-Run experiment").click().run()
    assert not at.exception, at.exception
    res = at.session_state.result
    assert res.config.n_pairs == 3000 and res.config.depolarizing_noise == pytest.approx(0.05)
    _button(at, "Tilted A1").click().run()
    assert at.session_state.lab_A1 == 60.0
    _button(at, "Reset all").click().run()
    assert not at.exception
    assert at.session_state.result.config.n_pairs == 5000


def test_eavesdropping_comparison():
    at = _open("eavesdropping")
    _button(at, "Run comparison").click().run()
    assert not at.exception, at.exception
    off, on = at.session_state.eve_comparison
    assert not off.config.eve.enabled and on.config.eve.enabled
    assert on.bell.s_value < off.bell.s_value
    _button(at, "Sweep the interception fraction from 0 to 1").click().run()
    assert not at.exception, at.exception
    assert len(at.session_state.eve_sweep) == 11


def test_reports_rerun_from_history():
    at = _open("reports")
    _button(at, "Re-run selected configuration").click().run()
    assert not at.exception, at.exception
