"""Pruebas unitarias de franjas y turnos (sin base de datos)."""

from datetime import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.appointment_windows import (
    MIN_SLOT_MINUTES,
    MAX_SLOT_MINUTES,
    _assert_slot_duration_valid,
    appointment_fits_in_windows,
    appointment_matches_slot,
    format_schedule_hint,
    iter_bookable_slots,
    slot_duration_minutes,
)


def _window(start_h: int, start_m: int, end_h: int, end_m: int):
    return SimpleNamespace(
        start_local=time(start_h, start_m),
        end_local=time(end_h, end_m),
    )


def test_slot_duration_minutes():
    assert slot_duration_minutes(time(8, 0), time(9, 30)) == 90


def test_iter_bookable_slots_returns_valid_turns():
    windows = [_window(8, 0, 9, 30), _window(10, 0, 10, 10)]  # segundo turno < 15 min
    slots = iter_bookable_slots(windows)
    assert len(slots) == 3
    assert (time(8, 0), time(9, 30), 90) in slots
    assert (time(8, 0), time(9, 0), 60) in slots
    assert (time(9, 0), time(9, 30), 30) in slots


def test_iter_bookable_slots_consecutive_in_long_window():
    windows = [_window(10, 1, 12, 0)]
    slots = iter_bookable_slots(windows)
    assert (time(10, 1), time(11, 1), 60) in slots
    assert (time(11, 1), time(12, 0), 59) in slots


def test_appointment_fits_in_windows():
    windows = [_window(10, 1, 12, 0)]
    assert appointment_fits_in_windows(time(10, 1), 60, windows) is True
    assert appointment_fits_in_windows(time(11, 1), 59, windows) is True
    assert appointment_fits_in_windows(time(9, 0), 60, windows) is False


def test_appointment_matches_slot_exact_turn():
    assert appointment_matches_slot(time(8, 0), 90, time(8, 0), time(9, 30)) is True
    assert appointment_matches_slot(time(8, 15), 90, time(8, 0), time(9, 30)) is False


def test_assert_slot_duration_too_short():
    with pytest.raises(HTTPException) as exc:
        _assert_slot_duration_valid(time(8, 0), time(8, 10), "Franja test")
    assert exc.value.status_code == 400
    assert str(MIN_SLOT_MINUTES) in exc.value.detail


def test_assert_slot_duration_too_long():
    with pytest.raises(HTTPException) as exc:
        _assert_slot_duration_valid(time(8, 0), time(17, 0), "Franja test")
    assert exc.value.status_code == 400
    assert str(MAX_SLOT_MINUTES) in exc.value.detail


def test_assert_slot_duration_valid_returns_minutes():
    assert _assert_slot_duration_valid(time(8, 0), time(9, 30)) == 90


def test_format_schedule_hint_empty():
    assert "Sin turnos" in format_schedule_hint([])


def test_format_schedule_hint_lists_turns():
    hint = format_schedule_hint([_window(8, 0, 9, 30)])
    assert "08:00" in hint
    assert "90 min" in hint
