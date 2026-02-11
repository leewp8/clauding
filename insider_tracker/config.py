"""Configuration management for insider trading tracker."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Optional

from insider_tracker.models import AlertThresholds


class Config:
    """Configuration manager for the tracker."""

    DEFAULT_DATA_DIR = Path.home() / ".insider-tracker"
    CONFIG_FILE = "config.json"

    # Default configuration values
    DEFAULTS = {
        "user_agent": "InsiderTracker/1.0 (your-email@example.com)",
        "scan_days": 7,
        "min_significance": "medium",
        "thresholds": {
            "min_transaction_value": "10000",
            "min_shares": 1000,
            "large_transaction_value": "100000",
            "significant_transaction_value": "500000",
            "critical_transaction_value": "1000000",
            "ownership_change_percent": "10",
            "cluster_window_days": 7,
            "cluster_min_insiders": 3,
        },
        "notifications": {
            "enabled": False,
            "email": None,
            "webhook_url": None,
        },
        "dashboard": {
            "output_path": None,
            "big_mover_threshold": 5.0,
            "newsapi_key": None,
            "insider_lookback_days": 30,
        },
    }

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize configuration.

        Args:
            data_dir: Directory to store configuration
        """
        self.data_dir = data_dir or self.DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.data_dir / self.CONFIG_FILE
        self._config = self._load()

    def _load(self) -> dict:
        """Load configuration from disk."""
        config = self.DEFAULTS.copy()

        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    saved = json.load(f)
                    # Merge saved config with defaults
                    self._deep_merge(config, saved)
            except Exception as e:
                print(f"Error loading config: {e}")

        return config

    def _deep_merge(self, base: dict, update: dict) -> None:
        """Deep merge update into base dict."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def save(self) -> None:
        """Save configuration to disk."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default=None):
        """Get a configuration value.

        Args:
            key: Configuration key (supports dot notation like 'thresholds.min_shares')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value) -> None:
        """Set a configuration value.

        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value
        self.save()

    @property
    def user_agent(self) -> str:
        """Get SEC user agent string."""
        return self.get("user_agent", self.DEFAULTS["user_agent"])

    @user_agent.setter
    def user_agent(self, value: str) -> None:
        """Set SEC user agent string."""
        self.set("user_agent", value)

    @property
    def scan_days(self) -> int:
        """Get default scan lookback days."""
        return self.get("scan_days", self.DEFAULTS["scan_days"])

    @scan_days.setter
    def scan_days(self, value: int) -> None:
        """Set default scan lookback days."""
        self.set("scan_days", value)

    @property
    def min_significance(self) -> str:
        """Get minimum significance level for alerts."""
        return self.get("min_significance", self.DEFAULTS["min_significance"])

    @min_significance.setter
    def min_significance(self, value: str) -> None:
        """Set minimum significance level."""
        self.set("min_significance", value)

    def get_thresholds(self) -> AlertThresholds:
        """Get alert thresholds as AlertThresholds object."""
        thresh = self.get("thresholds", self.DEFAULTS["thresholds"])
        return AlertThresholds(
            min_transaction_value=Decimal(str(thresh.get("min_transaction_value", "10000"))),
            min_shares=thresh.get("min_shares", 1000),
            large_transaction_value=Decimal(str(thresh.get("large_transaction_value", "100000"))),
            significant_transaction_value=Decimal(
                str(thresh.get("significant_transaction_value", "500000"))
            ),
            critical_transaction_value=Decimal(
                str(thresh.get("critical_transaction_value", "1000000"))
            ),
            ownership_change_percent=Decimal(str(thresh.get("ownership_change_percent", "10"))),
            cluster_window_days=thresh.get("cluster_window_days", 7),
            cluster_min_insiders=thresh.get("cluster_min_insiders", 3),
        )

    def set_threshold(self, name: str, value) -> None:
        """Set a specific threshold value.

        Args:
            name: Threshold name
            value: Threshold value
        """
        self.set(f"thresholds.{name}", str(value) if isinstance(value, Decimal) else value)

    @property
    def notifications_enabled(self) -> bool:
        """Check if notifications are enabled."""
        return self.get("notifications.enabled", False)

    @notifications_enabled.setter
    def notifications_enabled(self, value: bool) -> None:
        """Enable or disable notifications."""
        self.set("notifications.enabled", value)

    @property
    def notification_email(self) -> Optional[str]:
        """Get notification email."""
        return self.get("notifications.email")

    @notification_email.setter
    def notification_email(self, value: str) -> None:
        """Set notification email."""
        self.set("notifications.email", value)

    @property
    def webhook_url(self) -> Optional[str]:
        """Get webhook URL for notifications."""
        return self.get("notifications.webhook_url")

    @webhook_url.setter
    def webhook_url(self, value: str) -> None:
        """Set webhook URL."""
        self.set("notifications.webhook_url", value)

    @property
    def newsapi_key(self) -> Optional[str]:
        """Get NewsAPI.org API key."""
        return self.get("dashboard.newsapi_key")

    @newsapi_key.setter
    def newsapi_key(self, value: str) -> None:
        """Set NewsAPI.org API key."""
        self.set("dashboard.newsapi_key", value)

    @property
    def big_mover_threshold(self) -> float:
        """Get big mover threshold percentage."""
        return float(self.get("dashboard.big_mover_threshold", 5.0))

    @big_mover_threshold.setter
    def big_mover_threshold(self, value: float) -> None:
        """Set big mover threshold percentage."""
        self.set("dashboard.big_mover_threshold", value)

    @property
    def dashboard_output_path(self) -> Optional[str]:
        """Get dashboard output file path."""
        return self.get("dashboard.output_path")

    @dashboard_output_path.setter
    def dashboard_output_path(self, value: str) -> None:
        """Set dashboard output file path."""
        self.set("dashboard.output_path", value)

    def reset_to_defaults(self) -> None:
        """Reset all configuration to defaults."""
        self._config = self.DEFAULTS.copy()
        self.save()

    def to_dict(self) -> dict:
        """Get full configuration as dictionary."""
        return self._config.copy()
