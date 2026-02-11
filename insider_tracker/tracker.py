"""Main insider trading tracker orchestration."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

from insider_tracker.alerts import Alert, AlertManager
from insider_tracker.analyzer import ClusterAnalysis, TransactionAnalysis, TransactionAnalyzer
from insider_tracker.config import Config
from insider_tracker.models import AlertThresholds, InsiderTransaction, SignificanceLevel
from insider_tracker.sec_client import SECClient
from insider_tracker.watchlist import WatchlistManager


class InsiderTracker:
    """Main class for tracking insider trading activity."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        user_agent: Optional[str] = None,
        thresholds: Optional[AlertThresholds] = None,
    ):
        """Initialize the insider tracker.

        Args:
            data_dir: Directory to store data files
            user_agent: User agent for SEC requests
            thresholds: Alert thresholds configuration
        """
        self.data_dir = data_dir or Path.home() / ".insider-tracker"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.config = Config(data_dir=self.data_dir)
        self.sec_client = SECClient(user_agent=user_agent)
        self.watchlist = WatchlistManager(data_dir=self.data_dir, sec_client=self.sec_client)
        self.alert_manager = AlertManager(data_dir=self.data_dir)
        self.analyzer = TransactionAnalyzer(thresholds=thresholds)
        self.thresholds = thresholds or AlertThresholds()

    def scan_watchlist(
        self,
        days: int = 7,
        min_significance: SignificanceLevel = SignificanceLevel.MEDIUM,
    ) -> list[Alert]:
        """Scan all watchlist companies for insider activity.

        Args:
            days: Number of days to look back
            min_significance: Minimum significance to alert on

        Returns:
            List of new alerts created
        """
        alerts = []
        all_transactions = []

        # Scan each ticker in watchlist
        for entry in self.watchlist.get_all():
            ticker = entry.ticker
            cik = entry.cik

            # Fetch recent Form 4 filings
            transactions = self.sec_client.get_recent_form4_filings(
                cik=cik,
                ticker=ticker if not cik else None,
                days=days,
            )

            all_transactions.extend(transactions)

            # Analyze each transaction
            for transaction in transactions:
                analysis = self.analyzer.analyze_transaction(
                    transaction,
                    related_transactions=transactions,
                )

                # Create alert if significant
                if analysis.is_significant:
                    sig_order = [
                        SignificanceLevel.LOW,
                        SignificanceLevel.MEDIUM,
                        SignificanceLevel.HIGH,
                        SignificanceLevel.CRITICAL,
                    ]
                    if sig_order.index(analysis.significance) >= sig_order.index(min_significance):
                        alert = self.alert_manager.create_transaction_alert(analysis)
                        if alert:
                            alerts.append(alert)

        # Look for clusters
        clusters = self.analyzer.find_clusters(all_transactions)
        for cluster in clusters:
            sig_order = [
                SignificanceLevel.LOW,
                SignificanceLevel.MEDIUM,
                SignificanceLevel.HIGH,
                SignificanceLevel.CRITICAL,
            ]
            if sig_order.index(cluster.significance) >= sig_order.index(min_significance):
                alert = self.alert_manager.create_cluster_alert(cluster)
                alerts.append(alert)

        return alerts

    def scan_ticker(
        self,
        ticker: str,
        days: int = 30,
    ) -> tuple[list[InsiderTransaction], list[TransactionAnalysis]]:
        """Scan a specific ticker for insider activity.

        Args:
            ticker: Stock ticker symbol
            days: Number of days to look back

        Returns:
            Tuple of (transactions, analyses)
        """
        transactions = self.sec_client.get_recent_form4_filings(
            ticker=ticker,
            days=days,
        )

        analyses = []
        for transaction in transactions:
            analysis = self.analyzer.analyze_transaction(
                transaction,
                related_transactions=transactions,
            )
            analyses.append(analysis)

        return transactions, analyses

    def get_ticker_summary(
        self,
        ticker: str,
        days: int = 90,
    ) -> dict:
        """Get a summary of insider activity for a ticker.

        Args:
            ticker: Stock ticker symbol
            days: Number of days to look back

        Returns:
            Summary dictionary
        """
        transactions, analyses = self.scan_ticker(ticker, days)

        # Get stats
        stats = self.analyzer.get_summary_stats(transactions)

        # Get significant transactions
        significant = [a for a in analyses if a.is_significant]

        # Get insiders involved
        insiders = {}
        for t in transactions:
            key = t.insider.cik or t.insider.name
            if key not in insiders:
                insiders[key] = {
                    "name": t.insider.name,
                    "title": t.insider.officer_title,
                    "is_director": t.insider.is_director,
                    "is_officer": t.insider.is_officer,
                    "purchases": 0,
                    "sales": 0,
                    "total_bought": Decimal("0"),
                    "total_sold": Decimal("0"),
                }
            if t.is_purchase:
                insiders[key]["purchases"] += 1
                if t.total_value:
                    insiders[key]["total_bought"] += t.total_value
            elif t.is_sale:
                insiders[key]["sales"] += 1
                if t.total_value:
                    insiders[key]["total_sold"] += t.total_value

        return {
            "ticker": ticker.upper(),
            "period_days": days,
            "stats": stats,
            "significant_count": len(significant),
            "insiders": list(insiders.values()),
            "transactions": transactions,
            "analyses": analyses,
        }

    def add_to_watchlist(
        self,
        ticker: str,
        is_portfolio: bool = False,
        shares: Optional[Decimal] = None,
        cost_basis: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Add a ticker to the watchlist.

        Args:
            ticker: Stock ticker symbol
            is_portfolio: Whether this is a portfolio holding
            shares: Number of shares owned
            cost_basis: Average cost basis
            notes: User notes

        Returns:
            Dictionary with entry info and recent activity
        """
        entry = self.watchlist.add(
            ticker=ticker,
            is_portfolio=is_portfolio,
            shares_owned=shares,
            average_cost=cost_basis,
            notes=notes,
        )

        # Get recent activity preview
        transactions = self.sec_client.get_recent_form4_filings(
            ticker=ticker,
            days=30,
            limit=10,
        )

        return {
            "entry": entry,
            "recent_transactions": len(transactions),
            "message": f"Added {ticker.upper()} to {'portfolio' if is_portfolio else 'watchlist'}",
        }

    def remove_from_watchlist(self, ticker: str) -> bool:
        """Remove a ticker from the watchlist.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if removed
        """
        return self.watchlist.remove(ticker)

    def get_alerts(
        self,
        ticker: Optional[str] = None,
        unread_only: bool = False,
        min_significance: Optional[SignificanceLevel] = None,
        limit: int = 50,
    ) -> list[Alert]:
        """Get alerts.

        Args:
            ticker: Filter by ticker
            unread_only: Only unread alerts
            min_significance: Minimum significance level
            limit: Maximum alerts to return

        Returns:
            List of alerts
        """
        return self.alert_manager.get_alerts(
            ticker=ticker,
            unread_only=unread_only,
            significance=min_significance,
            limit=limit,
        )

    def get_portfolio_exposure(self) -> dict:
        """Get insider trading exposure analysis for portfolio.

        Returns:
            Dictionary with portfolio exposure analysis
        """
        portfolio = self.watchlist.get_portfolio()

        exposure = {
            "holdings": [],
            "total_insider_buys_30d": Decimal("0"),
            "total_insider_sells_30d": Decimal("0"),
            "net_insider_sentiment": "neutral",
            "high_activity_tickers": [],
        }

        for entry in portfolio:
            # Get recent activity
            transactions = self.sec_client.get_recent_form4_filings(
                ticker=entry.ticker,
                days=30,
                limit=50,
            )

            buys = sum(
                t.total_value or Decimal("0")
                for t in transactions
                if t.is_purchase
            )
            sells = sum(
                t.total_value or Decimal("0")
                for t in transactions
                if t.is_sale
            )

            exposure["total_insider_buys_30d"] += buys
            exposure["total_insider_sells_30d"] += sells

            holding_info = {
                "ticker": entry.ticker,
                "company": entry.company_name,
                "shares_owned": entry.shares_owned,
                "insider_buys_30d": buys,
                "insider_sells_30d": sells,
                "net_activity": buys - sells,
                "transaction_count": len(transactions),
            }
            exposure["holdings"].append(holding_info)

            if len(transactions) >= 5:
                exposure["high_activity_tickers"].append(entry.ticker)

        # Determine overall sentiment
        net = exposure["total_insider_buys_30d"] - exposure["total_insider_sells_30d"]
        if net > Decimal("100000"):
            exposure["net_insider_sentiment"] = "bullish"
        elif net < Decimal("-100000"):
            exposure["net_insider_sentiment"] = "bearish"
        else:
            exposure["net_insider_sentiment"] = "neutral"

        return exposure

    def get_status(self) -> dict:
        """Get overall tracker status.

        Returns:
            Status dictionary
        """
        return {
            "watchlist_count": len(self.watchlist.get_watchlist()),
            "portfolio_count": len(self.watchlist.get_portfolio()),
            "total_tracked": self.watchlist.count(),
            "unread_alerts": self.alert_manager.get_unread_count(),
            "data_dir": str(self.data_dir),
        }

    def get_dashboard_generator(self):
        """Get a dashboard generator instance.

        Returns:
            DashboardGenerator configured with this tracker's components
        """
        from insider_tracker.dashboard import DashboardGenerator

        return DashboardGenerator(
            config=self.config,
            watchlist=self.watchlist,
            sec_client=self.sec_client,
        )
