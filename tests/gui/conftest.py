"""Shared fixtures for the Qt GUI test suite.

Forces the offscreen Qt platform so the suite runs headless (CI, SSH) without a
display server. Must run before pytest-qt instantiates the QApplication.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from slurmhub.config import AppConfig, ProfileConfig, SSHConfig
from slurmhub.db import open_demo_database
from slurmhub.slurm.demo_data import DEMO_HOST, DEMO_USERNAME
from slurmhub.gui.controller import AppController


def _demo_config() -> AppConfig:
    return AppConfig(
        profiles={
            "demo": ProfileConfig(
                name="demo", ssh=SSHConfig(host=DEMO_HOST, username=DEMO_USERNAME)
            )
        }
    )


@pytest.fixture
def demo_controller():
    """A demo-backed AppController, torn down (SSH + DB closed) after the test."""
    controller = AppController(_demo_config(), demo=True, database=open_demo_database())
    yield controller
    controller.shutdown()
