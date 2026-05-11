"""Unit tests for FollowUp condition-window mapping."""

from agents.followup.tools import _CONDITION_WINDOWS


def test_chf_window():
    window = _CONDITION_WINDOWS.get("I50")
    assert window is not None
    specialty, timing, priority = window
    assert "Cardiology" in specialty
    assert "7 days" in timing
    assert priority == "urgent"


def test_tkr_window():
    window = _CONDITION_WINDOWS.get("Z96")
    assert window is not None
    assert "Orthopedic" in window[0]


def test_pneumonia_window():
    window = _CONDITION_WINDOWS.get("J18")
    assert window is not None
    assert "PCP" in window[0]
    assert "14 days" in window[1]


def test_asthma_window():
    window = _CONDITION_WINDOWS.get("J45")
    assert window is not None
    assert "PCP" in window[0] or "Pulmonology" in window[0]


def test_unknown_condition_no_window():
    assert _CONDITION_WINDOWS.get("Z99") is None
