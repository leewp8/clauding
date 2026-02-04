"""Alert system for significant insider transactions."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from insider_tracker.analyzer import ClusterAnalysis, TransactionAnalysis
from insider_tracker.models import InsiderTransaction, SignificanceLevel


class AlertType(str, Enum):
    """Type of alert."""

    TRANSACTION = "transaction"  # Single significant transaction
    CLUSTER = "cluster"  # Cluster of insider activity
    PURCHASE = "purchase"  # Notable purchase
    SALE = "sale"  # Notable sale
    CEO_CFO = "ceo_cfo"  # CEO/CFO activity
    LARGE_VALUE = "large_value"  # Large transaction value


@dataclass
class Alert:
    """An alert for significant insider activity."""

    id: str
    alert_type: AlertType
    ticker: str
    company_name: str
    significance: SignificanceLevel
    title: str
    description: str
    details: list[str]
    transaction: Optional[InsiderTransaction] = None
    cluster: Optional[ClusterAnalysis] = None
    created_at: datetime = field(default_factory=datetime.now)
    is_read: bool = False
    is_dismissed: bool = False

    def to_dict(self) -> dict:
        """Convert alert to dictionary for serialization."""
        return {
            "id": self.id,
            "alert_type": self.alert_type.value,
            "ticker": self.ticker,
            "company_name": self.company_name,
            "significance": self.significance.value,
            "title": self.title,
            "description": self.description,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
            "is_read": self.is_read,
            "is_dismissed": self.is_dismissed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Alert":
        """Create alert from dictionary."""
        return cls(
            id=data["id"],
            alert_type=AlertType(data["alert_type"]),
            ticker=data["ticker"],
            company_name=data["company_name"],
            significance=SignificanceLevel(data["significance"]),
            title=data["title"],
            description=data["description"],
            details=data["details"],
            created_at=datetime.fromisoformat(data["created_at"]),
            is_read=data.get("is_read", False),
            is_dismissed=data.get("is_dismissed", False),
        )


# Type alias for alert callbacks
AlertCallback = Callable[[Alert], None]


class AlertManager:
    """Manages alerts for insider trading activity."""

    DEFAULT_DATA_DIR = Path.home() / ".insider-tracker"
    ALERTS_FILE = "alerts.json"
    SEEN_FILE = "seen_transactions.json"

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize alert manager.

        Args:
            data_dir: Directory to store alert data
        """
        self.data_dir = data_dir or self.DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_path = self.data_dir / self.ALERTS_FILE
        self.seen_path = self.data_dir / self.SEEN_FILE

        self._alerts: list[Alert] = []
        self._seen_transactions: set[str] = set()
        self._callbacks: list[AlertCallback] = []
        self._alert_counter = 0

        self._load()

    def _load(self) -> None:
        """Load alerts and seen transactions from disk."""
        # Load alerts
        if self.alerts_path.exists():
            try:
                with open(self.alerts_path, "r") as f:
                    data = json.load(f)
                    self._alerts = [Alert.from_dict(a) for a in data.get("alerts", [])]
                    self._alert_counter = data.get("counter", 0)
            except Exception as e:
                print(f"Error loading alerts: {e}")
                self._alerts = []

        # Load seen transactions
        if self.seen_path.exists():
            try:
                with open(self.seen_path, "r") as f:
                    data = json.load(f)
                    self._seen_transactions = set(data.get("seen", []))
            except Exception as e:
                print(f"Error loading seen transactions: {e}")
                self._seen_transactions = set()

    def _save(self) -> None:
        """Save alerts and seen transactions to disk."""
        try:
            # Save alerts
            with open(self.alerts_path, "w") as f:
                json.dump(
                    {
                        "alerts": [a.to_dict() for a in self._alerts],
                        "counter": self._alert_counter,
                    },
                    f,
                    indent=2,
                )

            # Save seen transactions
            with open(self.seen_path, "w") as f:
                json.dump({"seen": list(self._seen_transactions)}, f)
        except Exception as e:
            print(f"Error saving alerts: {e}")

    def _generate_id(self) -> str:
        """Generate a unique alert ID."""
        self._alert_counter += 1
        return f"alert_{self._alert_counter:06d}"

    def register_callback(self, callback: AlertCallback) -> None:
        """Register a callback for new alerts.

        Args:
            callback: Function to call when a new alert is created
        """
        self._callbacks.append(callback)

    def unregister_callback(self, callback: AlertCallback) -> None:
        """Unregister an alert callback.

        Args:
            callback: The callback to remove
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self, alert: Alert) -> None:
        """Notify all registered callbacks of a new alert."""
        for callback in self._callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"Error in alert callback: {e}")

    def is_seen(self, transaction: InsiderTransaction) -> bool:
        """Check if a transaction has already been seen.

        Args:
            transaction: The transaction to check

        Returns:
            True if already seen
        """
        key = f"{transaction.accession_number}:{transaction.insider.cik}"
        return key in self._seen_transactions

    def mark_seen(self, transaction: InsiderTransaction) -> None:
        """Mark a transaction as seen.

        Args:
            transaction: The transaction to mark
        """
        key = f"{transaction.accession_number}:{transaction.insider.cik}"
        self._seen_transactions.add(key)
        self._save()

    def create_transaction_alert(
        self,
        analysis: TransactionAnalysis,
    ) -> Optional[Alert]:
        """Create an alert from a transaction analysis.

        Args:
            analysis: The transaction analysis

        Returns:
            Created Alert or None if transaction was already seen
        """
        transaction = analysis.transaction

        # Skip if already seen
        if self.is_seen(transaction):
            return None

        # Determine alert type
        if transaction.is_purchase:
            alert_type = AlertType.PURCHASE
        elif transaction.is_sale:
            alert_type = AlertType.SALE
        else:
            alert_type = AlertType.TRANSACTION

        # Check for CEO/CFO
        from insider_tracker.models import InsiderRole

        if InsiderRole.CEO in transaction.insider.roles or InsiderRole.CFO in transaction.insider.roles:
            alert_type = AlertType.CEO_CFO

        # Build title
        action = "bought" if transaction.is_purchase else "sold"
        insider_name = transaction.insider.name
        title = f"{insider_name} {action} {transaction.company.ticker}"

        # Build description
        value_str = ""
        if transaction.total_value:
            value_str = f" (${transaction.total_value:,.0f})"
        shares_str = f"{transaction.shares:,.0f} shares"
        description = f"{insider_name} {action} {shares_str}{value_str}"

        # Build details
        details = analysis.reasons.copy()
        if transaction.insider.officer_title:
            details.insert(0, f"Title: {transaction.insider.officer_title}")
        if transaction.transaction_date:
            details.append(f"Transaction date: {transaction.transaction_date.strftime('%Y-%m-%d')}")
        details.append(f"Filing date: {transaction.filing_date.strftime('%Y-%m-%d')}")

        alert = Alert(
            id=self._generate_id(),
            alert_type=alert_type,
            ticker=transaction.company.ticker,
            company_name=transaction.company.name,
            significance=analysis.significance,
            title=title,
            description=description,
            details=details,
            transaction=transaction,
        )

        self._alerts.append(alert)
        self.mark_seen(transaction)
        self._save()
        self._notify_callbacks(alert)

        return alert

    def create_cluster_alert(self, cluster: ClusterAnalysis) -> Alert:
        """Create an alert from a cluster analysis.

        Args:
            cluster: The cluster analysis

        Returns:
            Created Alert
        """
        # Build title
        direction = cluster.net_direction
        title = f"Insider {direction} cluster: {cluster.ticker}"

        # Build description
        value_str = ""
        if cluster.total_value:
            value_str = f" totaling ${cluster.total_value:,.0f}"
        description = (
            f"{cluster.unique_insiders} insiders {direction} "
            f"{cluster.total_shares:,.0f} shares{value_str}"
        )

        # Build details
        details = cluster.reasons.copy()
        details.append(
            f"Period: {cluster.start_date.strftime('%Y-%m-%d')} to "
            f"{cluster.end_date.strftime('%Y-%m-%d')}"
        )

        alert = Alert(
            id=self._generate_id(),
            alert_type=AlertType.CLUSTER,
            ticker=cluster.ticker,
            company_name=cluster.company_name,
            significance=cluster.significance,
            title=title,
            description=description,
            details=details,
            cluster=cluster,
        )

        self._alerts.append(alert)
        self._save()
        self._notify_callbacks(alert)

        return alert

    def get_alerts(
        self,
        ticker: Optional[str] = None,
        unread_only: bool = False,
        significance: Optional[SignificanceLevel] = None,
        limit: int = 100,
    ) -> list[Alert]:
        """Get alerts with optional filtering.

        Args:
            ticker: Filter by ticker symbol
            unread_only: Only return unread alerts
            significance: Filter by minimum significance level
            limit: Maximum number of alerts to return

        Returns:
            List of alerts
        """
        alerts = self._alerts.copy()

        # Filter dismissed
        alerts = [a for a in alerts if not a.is_dismissed]

        # Apply filters
        if ticker:
            ticker = ticker.upper()
            alerts = [a for a in alerts if a.ticker == ticker]

        if unread_only:
            alerts = [a for a in alerts if not a.is_read]

        if significance:
            sig_order = [
                SignificanceLevel.LOW,
                SignificanceLevel.MEDIUM,
                SignificanceLevel.HIGH,
                SignificanceLevel.CRITICAL,
            ]
            min_index = sig_order.index(significance)
            alerts = [a for a in alerts if sig_order.index(a.significance) >= min_index]

        # Sort by date (newest first)
        alerts.sort(key=lambda a: a.created_at, reverse=True)

        return alerts[:limit]

    def get_unread_count(self, ticker: Optional[str] = None) -> int:
        """Get count of unread alerts.

        Args:
            ticker: Filter by ticker symbol

        Returns:
            Count of unread alerts
        """
        return len(self.get_alerts(ticker=ticker, unread_only=True, limit=1000))

    def mark_read(self, alert_id: str) -> bool:
        """Mark an alert as read.

        Args:
            alert_id: The alert ID

        Returns:
            True if found and marked
        """
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.is_read = True
                self._save()
                return True
        return False

    def mark_all_read(self, ticker: Optional[str] = None) -> int:
        """Mark all alerts as read.

        Args:
            ticker: Filter by ticker symbol

        Returns:
            Number of alerts marked
        """
        count = 0
        for alert in self._alerts:
            if ticker and alert.ticker != ticker.upper():
                continue
            if not alert.is_read:
                alert.is_read = True
                count += 1

        if count > 0:
            self._save()
        return count

    def dismiss(self, alert_id: str) -> bool:
        """Dismiss an alert.

        Args:
            alert_id: The alert ID

        Returns:
            True if found and dismissed
        """
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.is_dismissed = True
                self._save()
                return True
        return False

    def clear_old_alerts(self, days: int = 30) -> int:
        """Clear alerts older than specified days.

        Args:
            days: Age in days to clear

        Returns:
            Number of alerts cleared
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=days)
        original_count = len(self._alerts)
        self._alerts = [a for a in self._alerts if a.created_at >= cutoff]
        cleared = original_count - len(self._alerts)

        if cleared > 0:
            self._save()
        return cleared

    def clear_seen_transactions(self, days: int = 90) -> None:
        """Clear old seen transaction records.

        Note: This doesn't have access to timestamps, so it clears all.
        In a production system, you'd store timestamps with seen transactions.

        Args:
            days: Not used currently, kept for API compatibility
        """
        self._seen_transactions.clear()
        self._save()
