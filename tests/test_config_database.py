"""Tests for the [database] config section and its backwards-compatibility."""

import tomllib

from slurmhub.config import (
    AppConfig,
    ConfigLoader,
    DatabaseConfig,
    ProfileConfig,
    SSHConfig,
    _from_legacy_json,
    _from_toml_dict,
)


class TestDatabaseConfigParsing:
    def test_full_section_parses(self):
        data = {
            "profiles": {"c": {"host": "h"}},
            "database": {
                "enabled": False,
                "path": "/tmp/x.db",
                "retention_days": 14,
                "capture_utilization": False,
                "utilization_interval": 120,
            },
        }
        cfg = _from_toml_dict(data)
        assert cfg.database.enabled is False
        assert cfg.database.path == "/tmp/x.db"
        assert cfg.database.retention_days == 14
        assert cfg.database.capture_utilization is False
        assert cfg.database.utilization_interval == 120

    def test_absent_section_uses_defaults(self):
        cfg = _from_toml_dict({"profiles": {"c": {"host": "h"}}})
        assert cfg.database.enabled is True
        assert cfg.database.retention_days == 0
        assert cfg.database.capture_utilization is True

    def test_partial_section_keeps_other_defaults(self):
        cfg = _from_toml_dict(
            {"profiles": {"c": {"host": "h"}}, "database": {"enabled": False}}
        )
        assert cfg.database.enabled is False
        assert cfg.database.retention_days == 0  # default preserved

    def test_max_age_days_alias(self):
        cfg = _from_toml_dict(
            {"profiles": {"c": {"host": "h"}}, "database": {"max_age_days": 7}}
        )
        assert cfg.database.retention_days == 7

    def test_legacy_json_gets_default_database(self):
        cfg = _from_legacy_json({"remote_host": "h"})
        assert isinstance(cfg.database, DatabaseConfig)
        assert cfg.database.enabled is True

    def test_appconfig_default_database(self):
        # Every construction site (CLI-built configs etc.) gets a default.
        assert AppConfig(profiles={}).database.enabled is True


class TestDatabaseConfigRoundTrip:
    def test_save_toml_round_trips_non_default_database(self, tmp_path):
        cfg = AppConfig(
            profiles={"c": ProfileConfig(name="c", ssh=SSHConfig(host="h"))},
            database=DatabaseConfig(enabled=False, retention_days=30),
        )
        path = tmp_path / "config.toml"
        ConfigLoader.save_toml(cfg, path)

        # The section is present and parseable...
        raw = tomllib.loads(path.read_text())
        assert raw["database"]["enabled"] is False
        assert raw["database"]["retention_days"] == 30

        # ...and reloads to the same values.
        reloaded = ConfigLoader.load(path)
        assert reloaded.database.enabled is False
        assert reloaded.database.retention_days == 30

    def test_save_toml_omits_default_database(self, tmp_path):
        cfg = AppConfig(
            profiles={"c": ProfileConfig(name="c", ssh=SSHConfig(host="h"))},
        )
        path = tmp_path / "config.toml"
        ConfigLoader.save_toml(cfg, path)
        assert "[database]" not in path.read_text()
