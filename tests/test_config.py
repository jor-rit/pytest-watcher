from argparse import Namespace
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from pytest_watcher.config import find_config, parse_config
from pytest_watcher.constants import DEFAULT_DELAY

from pytest_watcher.watcher import Config


@pytest.fixture(autouse=True)
def _patch_cwd(mocker: MockerFixture, tmp_path: Path):
    mock = mocker.patch("pytest_watcher.config.Path.cwd")
    mock.return_value = tmp_path


@pytest.fixture
def empty_namespace(tmp_path: Path):
    return Namespace(
        path=tmp_path,
        now=None,
        delay=None,
        runner=None,
        patterns=None,
        ignore_patterns=None,
    )


@pytest.fixture
def config(empty_namespace: Namespace) -> Config:
    return Config.create(empty_namespace)


@pytest.fixture
def pyproject_toml(pyproject_toml_path: Path) -> Path:
    pyproject_toml_path.write_text(
        "[tool.pytest_watcher]\n"
        "now = true\n"
        "delay = 999\n"
        "runner = 'tox'\n"
        "runner_args = ['--lf', '--nf']\n"
        "patterns = ['*.py', '.env']\n"
        "ignore_patterns = ['ignore.py']\n"
    )

    return pyproject_toml_path


@pytest.fixture
def namespace(tmp_path: Path) -> Namespace:
    return Namespace(
        path=tmp_path,
        now=True,
        delay=20,
        runner="tox",
        patterns=["*.py", ".env"],
        ignore_patterns=["main.py"],
    )


def test_default_values(config: Config):
    assert config.now is False
    assert config.delay == DEFAULT_DELAY
    assert config.runner == "pytest"
    assert config.runner_args == []
    assert config.patterns == []
    assert config.ignore_patterns == []


def test_cli_args(namespace: Namespace, tmp_path: Path):
    runner_args = ["--lf", "--nf"]

    config = Config.create(namespace=namespace, extra_args=runner_args)

    for f in config.CONFIG_FIELDS:
        assert getattr(config, f) == getattr(namespace, f)

    assert config.runner_args == runner_args


def test_cli_args_none_values_are_skipped(tmp_path: Path):
    namespace = Namespace(
        path=tmp_path,
        now=None,
        delay=None,
        runner=None,
        patterns=None,
        ignore_patterns=None,
    )

    config = Config.create(namespace=namespace, extra_args=None)

    for f in config.CONFIG_FIELDS:
        assert getattr(config, f) is not None

    assert config.runner_args == []


def test_pyproject_toml(pyproject_toml: Path, config: Config):
    assert config.now is True
    assert config.delay == 999
    assert config.runner == "tox"
    assert config.runner_args == ["--lf", "--nf"]
    assert config.patterns == ["*.py", ".env"]
    assert config.ignore_patterns == ["ignore.py"]


def test_cli_args_preferred_over_pyproject_toml(
    pyproject_toml: Path, namespace: Namespace
):
    extra_args = ["--cli", "--args"]

    config = Config.create(namespace, extra_args=extra_args)

    for f in Config.CONFIG_FIELDS:
        assert getattr(config, f) == getattr(namespace, f)

    assert config.runner_args == extra_args


@pytest.mark.parametrize(
    ("work_dir"),
    [
        Path(""),
        Path("test/"),
        Path("test/nested/dir/"),
    ],
)
def test_find_config(
    tmp_path: Path, pyproject_toml_path: Path, work_dir: Path, mocker: MockerFixture
):
    work_dir = tmp_path.joinpath(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    got = find_config(tmp_path)
    assert got == pyproject_toml_path, "Config file not found"


def test_parse_config_no_section(pyproject_toml_path: Path):
    pyproject_toml_path.write_text("[tool.another_section]\ndelay = 2\nrunner = 'tox'\n")

    got = parse_config(pyproject_toml_path)

    assert got == {}


def test_parse_config_parse_error(pyproject_toml_path: Path):
    pyproject_toml_path.write_text(
        "[tool.another_section]\n" "delay = 2\nrunner = invalid\n"
    )

    with pytest.raises(SystemExit):
        parse_config(pyproject_toml_path)
