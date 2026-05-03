"""Tests for DEMO_MODE helper and settings."""

import importlib

import pytest


def test_settings_default_demo_mode_false(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    from app import config
    importlib.reload(config)
    assert config.settings.demo_mode is False


def test_settings_demo_mode_true_from_env(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    from app import config
    importlib.reload(config)
    assert config.settings.demo_mode is True


def test_guest_user_has_full_access(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    from app import config
    importlib.reload(config)
    from app.core.demo import GUEST_USER
    assert GUEST_USER.has_full_access is True
    assert GUEST_USER.is_admin is False
    assert GUEST_USER.email == "guest@demo.ynfactory.online"
