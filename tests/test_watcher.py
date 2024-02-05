import sys
from pathlib import Path
from unittest.mock import MagicMock, sentinel

import pytest
from freezegun import freeze_time
from pytest_mock.plugin import MockerFixture

from pytest_watcher import watcher
from pytest_watcher.constants import DEFAULT_DELAY, LOOP_DELAY


@pytest.fixture(autouse=True)
def _release():
    """Reset trigger after each test"""
    try:
        yield
    finally:
        watcher.trigger.release()


@freeze_time("2020-01-01 00:00:00")
def test_main_loop_does_not_invoke_runner_without_trigger(
    mock_subprocess_run: MagicMock,
    mock_time_sleep: MagicMock,
):
    watcher.trigger.emit()

    watcher.main_loop(runner="pytest", runner_args=["--lf"], delay=5, clear=False)

    mock_subprocess_run.assert_not_called()
    mock_time_sleep.assert_called_once_with(LOOP_DELAY)

    assert not watcher.trigger.is_empty()


@freeze_time("2020-01-01 00:00:00")
def test_main_loop_does_not_invoke_runner_before_delay(
    mock_subprocess_run: MagicMock, mock_time_sleep: MagicMock
):
    watcher.trigger.emit()

    with freeze_time("2020-01-01 00:00:04"):
        watcher.main_loop(runner="pytest", runner_args=["--lf"], delay=5, clear=False)

    mock_subprocess_run.assert_not_called()
    mock_time_sleep.assert_called_once_with(LOOP_DELAY)

    assert not watcher.trigger.is_empty()


@freeze_time("2020-01-01 00:00:00")
def test_main_loop_invokes_runner_after_delay(
    mock_subprocess_run: MagicMock, mock_time_sleep: MagicMock
):
    watcher.trigger.emit()

    with freeze_time("2020-01-01 00:00:06"):
        watcher.main_loop(runner="pytest", runner_args=["--lf"], delay=5, clear=False)

    mock_subprocess_run.assert_called_once_with(["pytest", "--lf"])
    mock_time_sleep.assert_called_once_with(LOOP_DELAY)

    assert watcher.trigger.is_empty()


def test_main_loop_keystroke(
    mock_subprocess_run: MagicMock,
    mock_time_sleep: MagicMock,
    mock_handle_keystroke: MagicMock,
    mock_term_utils: MagicMock,
):
    watcher.trigger.emit()
    mock_term_utils.capture_keystroke.return_value = sentinel.KEYSTROKE

    watcher.main_loop(runner="pytest", runner_args=["--lf"], delay=5, clear=False)

    mock_handle_keystroke.assert_called_once_with(sentinel.KEYSTROKE, ["--lf"])


def assert_observer_started(mock_observer: MagicMock, expected_path: Path):
    mock_observer.assert_called_once_with()
    observer_instance = mock_observer.return_value
    observer_instance.schedule.assert_called_once()
    observer_instance.start.assert_called_once()

    path = mock_observer.return_value.schedule.call_args[0][1]
    assert path == expected_path


def test_run_starts_the_observer_and_main_loop(
    mocker: MockerFixture,
    mock_observer: MagicMock,
    mock_main_loop: MagicMock,
):
    args = ["ptw", ".", "--lf", "--nf"]

    mocker.patch.object(sys, "argv", args)

    with pytest.raises(InterruptedError):
        watcher.run()

    assert_observer_started(mock_observer, Path("."))

    mock_main_loop.assert_called_once_with(
        runner="pytest", runner_args=["--lf", "--nf"], delay=DEFAULT_DELAY, clear=False
    )


def test_run_invokes_tests_right_away_if_now_flag_is_set(
    mocker: MockerFixture,
    mock_observer: MagicMock,
    mock_main_loop: MagicMock,
):
    args = ["ptw", ".", "--lf", "--nf", "--now"]

    mocker.patch.object(sys, "argv", args)

    with pytest.raises(InterruptedError):
        watcher.run()

    assert not watcher.trigger.is_empty()


def test_custom_runner_is_passed_to_main_loop(
    mocker: MockerFixture,
    mock_observer: MagicMock,
    mock_main_loop: MagicMock,
):
    custom_runner = "tox"
    args = ["ptw", ".", "--lf", "--nf", "--now", "--runner", custom_runner]

    mocker.patch.object(sys, "argv", args)

    with pytest.raises(InterruptedError):
        watcher.run()

    assert_observer_started(mock_observer, Path("."))

    mock_main_loop.assert_called_once_with(
        runner=custom_runner,
        runner_args=["--lf", "--nf"],
        delay=DEFAULT_DELAY,
        clear=False,
    )


def test_clear_is_passed_to_main_loop(
    mocker: MockerFixture,
    mock_observer: MagicMock,
    mock_main_loop: MagicMock,
):
    args = ["ptw", ".", "--clear"]

    mocker.patch.object(sys, "argv", args)

    with pytest.raises(InterruptedError):
        watcher.run()

    mock_main_loop.assert_called_once_with(
        runner="pytest", runner_args=[], delay=DEFAULT_DELAY, clear=True
    )


def test_patterns_and_ignore_patterns_are_passed_to_event_handler(
    mocker: MockerFixture,
    mock_observer: MagicMock,
    mock_main_loop: MagicMock,
):
    args = ["ptw", ".", "--patterns", "*.py,.env", "--ignore-patterns", "settings.py"]

    mocker.patch.object(sys, "argv", args)

    with pytest.raises(InterruptedError):
        watcher.run()

    event_handler = mock_observer.return_value.schedule.call_args[0][0]

    assert event_handler.patterns == ["*.py", ".env"]
    assert event_handler.ignore_patterns == ["settings.py"]
