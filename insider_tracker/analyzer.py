"""Transaction analysis and significance detection."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from insider_tracker.models import (
    AlertThresholds,
    InsiderRole,
    InsiderTransaction,
    SignificanceLevel,
    TransactionType,
)


@dataclass
class TransactionAnalysis:
    """Analysis results for a transaction."""

    transaction: InsiderTransaction
    significance: SignificanceLevel
    reasons: list[str] = field(default_factory=list)
    score: int = 0  # Higher score = more significant

    @property
    def is_significant(self) -> bool:
        """Check if transaction is significant enough to alert."""
        return self.significance in [
            SignificanceLevel.MEDIUM,
            SignificanceLevel.HIGH,
            SignificanceLevel.CRITICAL,
        ]


@dataclass
class ClusterAnalysis:
    """Analysis of clustered insider activity."""

    ticker: str
    company_name: str
    transactions: list[InsiderTransaction]
    unique_insiders: int
    total_shares: Decimal
    total_value: Optional[Decimal]
    net_direction: str  # "buying", "selling", "mixed"
    start_date: datetime
    end_date: datetime
    significance: SignificanceLevel
    reasons: list[str] = field(default_factory=list)


class TransactionAnalyzer:
    """Analyzes insider transactions for significance."""

    # Weights for different factors
    WEIGHTS = {
        "ceo_cfo": 30,  # CEO/CFO transactions
        "director": 15,  # Director transactions
        "ten_percent_owner": 20,  # 10% owner transactions
        "officer": 10,  # Other officers
        "large_value": 25,  # Large transaction value
        "significant_value": 40,  # Significant transaction value
        "critical_value": 60,  # Critical transaction value
        "open_market": 20,  # Open market (vs. options exercise)
        "purchase": 15,  # Purchases are generally more significant
        "ownership_change": 25,  # Large ownership percentage change
        "multiple_transactions": 10,  # Multiple transactions same day
    }

    def __init__(self, thresholds: Optional[AlertThresholds] = None):
        """Initialize analyzer.

        Args:
            thresholds: Alert thresholds configuration
        """
        self.thresholds = thresholds or AlertThresholds()

    def analyze_transaction(
        self,
        transaction: InsiderTransaction,
        related_transactions: Optional[list[InsiderTransaction]] = None,
    ) -> TransactionAnalysis:
        """Analyze a single transaction for significance.

        Args:
            transaction: The transaction to analyze
            related_transactions: Other recent transactions for context

        Returns:
            TransactionAnalysis with significance assessment
        """
        reasons = []
        score = 0

        # Skip non-open-market transactions with zero value
        if (
            not transaction.is_open_market
            and (transaction.total_value is None or transaction.total_value == 0)
        ):
            return TransactionAnalysis(
                transaction=transaction,
                significance=SignificanceLevel.LOW,
                reasons=["Non-open-market transaction with no value"],
                score=0,
            )

        # Analyze insider role
        insider = transaction.insider
        if InsiderRole.CEO in insider.roles or InsiderRole.CFO in insider.roles:
            score += self.WEIGHTS["ceo_cfo"]
            role_name = "CEO" if InsiderRole.CEO in insider.roles else "CFO"
            reasons.append(f"{role_name} transaction")
        elif insider.is_director:
            score += self.WEIGHTS["director"]
            reasons.append("Director transaction")
        elif insider.is_ten_percent_owner:
            score += self.WEIGHTS["ten_percent_owner"]
            reasons.append("10% owner transaction")
        elif insider.is_officer:
            score += self.WEIGHTS["officer"]
            reasons.append("Officer transaction")

        # Analyze transaction type
        if transaction.is_open_market:
            score += self.WEIGHTS["open_market"]
            reasons.append("Open market transaction")

        if transaction.is_purchase:
            score += self.WEIGHTS["purchase"]
            reasons.append("Purchase (insider buying)")

        # Analyze transaction value
        if transaction.total_value:
            value = transaction.total_value
            if value >= self.thresholds.critical_transaction_value:
                score += self.WEIGHTS["critical_value"]
                reasons.append(f"Critical value: ${value:,.0f}")
            elif value >= self.thresholds.significant_transaction_value:
                score += self.WEIGHTS["significant_value"]
                reasons.append(f"Significant value: ${value:,.0f}")
            elif value >= self.thresholds.large_transaction_value:
                score += self.WEIGHTS["large_value"]
                reasons.append(f"Large value: ${value:,.0f}")

        # Analyze ownership change
        if transaction.shares_owned_after and transaction.shares:
            if transaction.shares_owned_after > 0:
                if transaction.acquired_disposed == "A":
                    # Purchase - calculate percentage increase
                    prev_shares = transaction.shares_owned_after - transaction.shares
                    if prev_shares > 0:
                        pct_change = (transaction.shares / prev_shares) * 100
                        if pct_change >= self.thresholds.ownership_change_percent:
                            score += self.WEIGHTS["ownership_change"]
                            reasons.append(f"Ownership increased by {pct_change:.1f}%")
                else:
                    # Sale - calculate percentage decrease
                    prev_shares = transaction.shares_owned_after + transaction.shares
                    if prev_shares > 0:
                        pct_change = (transaction.shares / prev_shares) * 100
                        if pct_change >= self.thresholds.ownership_change_percent:
                            score += self.WEIGHTS["ownership_change"]
                            reasons.append(f"Ownership decreased by {pct_change:.1f}%")

        # Check for multiple transactions by same insider
        if related_transactions:
            same_day = [
                t
                for t in related_transactions
                if t.transaction_date == transaction.transaction_date
                and t.insider.cik == transaction.insider.cik
                and t.accession_number != transaction.accession_number
            ]
            if same_day:
                score += self.WEIGHTS["multiple_transactions"]
                reasons.append(f"Multiple transactions same day ({len(same_day) + 1} total)")

        # Determine significance level
        significance = self._score_to_significance(score)

        return TransactionAnalysis(
            transaction=transaction,
            significance=significance,
            reasons=reasons,
            score=score,
        )

    def _score_to_significance(self, score: int) -> SignificanceLevel:
        """Convert score to significance level."""
        if score >= 80:
            return SignificanceLevel.CRITICAL
        elif score >= 50:
            return SignificanceLevel.HIGH
        elif score >= 25:
            return SignificanceLevel.MEDIUM
        else:
            return SignificanceLevel.LOW

    def analyze_cluster(
        self,
        transactions: list[InsiderTransaction],
        ticker: str,
        company_name: str = "",
    ) -> Optional[ClusterAnalysis]:
        """Analyze a cluster of transactions for coordinated activity.

        Args:
            transactions: List of transactions to analyze
            ticker: Stock ticker symbol
            company_name: Company name

        Returns:
            ClusterAnalysis if cluster is significant, None otherwise
        """
        if not transactions:
            return None

        # Group by time window
        window_days = self.thresholds.cluster_window_days
        min_insiders = self.thresholds.cluster_min_insiders

        # Get unique insiders
        unique_insiders = set()
        for t in transactions:
            unique_insiders.add(t.insider.cik or t.insider.name)

        if len(unique_insiders) < min_insiders:
            return None

        # Calculate totals
        total_shares = Decimal("0")
        total_value = Decimal("0")
        purchases = 0
        sales = 0

        dates = []
        for t in transactions:
            total_shares += t.shares
            if t.total_value:
                total_value += t.total_value
            if t.is_purchase:
                purchases += 1
            elif t.is_sale:
                sales += 1
            if t.transaction_date:
                dates.append(t.transaction_date)
            else:
                dates.append(t.filing_date)

        # Determine net direction
        if purchases > 0 and sales == 0:
            net_direction = "buying"
        elif sales > 0 and purchases == 0:
            net_direction = "selling"
        else:
            net_direction = "mixed"

        # Calculate date range
        start_date = min(dates) if dates else datetime.now()
        end_date = max(dates) if dates else datetime.now()

        # Determine significance
        reasons = []
        reasons.append(f"{len(unique_insiders)} insiders {net_direction}")
        reasons.append(f"Total shares: {total_shares:,.0f}")
        if total_value > 0:
            reasons.append(f"Total value: ${total_value:,.0f}")

        # Score cluster significance
        score = 0
        score += len(unique_insiders) * 15  # More insiders = more significant

        if net_direction != "mixed":
            score += 20  # Coordinated direction is significant
            reasons.append(f"Coordinated {net_direction} activity")

        if total_value >= self.thresholds.critical_transaction_value:
            score += 40
        elif total_value >= self.thresholds.significant_transaction_value:
            score += 25

        significance = self._score_to_significance(score)

        return ClusterAnalysis(
            ticker=ticker,
            company_name=company_name,
            transactions=transactions,
            unique_insiders=len(unique_insiders),
            total_shares=total_shares,
            total_value=total_value if total_value > 0 else None,
            net_direction=net_direction,
            start_date=start_date,
            end_date=end_date,
            significance=significance,
            reasons=reasons,
        )

    def find_clusters(
        self,
        transactions: list[InsiderTransaction],
    ) -> list[ClusterAnalysis]:
        """Find clusters of insider activity across companies.

        Args:
            transactions: List of transactions to analyze

        Returns:
            List of ClusterAnalysis objects for significant clusters
        """
        clusters = []

        # Group transactions by company
        by_company: dict[str, list[InsiderTransaction]] = defaultdict(list)
        for t in transactions:
            by_company[t.company.ticker].append(t)

        # Analyze each company for clusters
        for ticker, company_transactions in by_company.items():
            if not company_transactions:
                continue

            company_name = company_transactions[0].company.name

            # Sort by date
            sorted_trans = sorted(
                company_transactions,
                key=lambda t: t.transaction_date or t.filing_date,
            )

            # Find clusters using sliding window
            window_days = self.thresholds.cluster_window_days
            i = 0
            while i < len(sorted_trans):
                # Find all transactions within window
                window_start = sorted_trans[i].transaction_date or sorted_trans[i].filing_date
                window_end = window_start + timedelta(days=window_days)

                window_trans = []
                j = i
                while j < len(sorted_trans):
                    trans_date = sorted_trans[j].transaction_date or sorted_trans[j].filing_date
                    if trans_date <= window_end:
                        window_trans.append(sorted_trans[j])
                        j += 1
                    else:
                        break

                # Analyze window
                cluster = self.analyze_cluster(window_trans, ticker, company_name)
                if cluster and cluster.significance != SignificanceLevel.LOW:
                    clusters.append(cluster)
                    i = j  # Skip to end of cluster
                else:
                    i += 1

        return clusters

    def get_summary_stats(
        self,
        transactions: list[InsiderTransaction],
    ) -> dict:
        """Get summary statistics for a list of transactions.

        Args:
            transactions: List of transactions

        Returns:
            Dictionary of summary statistics
        """
        if not transactions:
            return {
                "total_transactions": 0,
                "purchases": 0,
                "sales": 0,
                "total_purchase_value": Decimal("0"),
                "total_sale_value": Decimal("0"),
                "unique_insiders": 0,
                "unique_companies": 0,
            }

        purchases = []
        sales = []
        insiders = set()
        companies = set()

        for t in transactions:
            insiders.add(t.insider.cik or t.insider.name)
            companies.add(t.company.ticker)

            if t.is_purchase:
                purchases.append(t)
            elif t.is_sale:
                sales.append(t)

        purchase_value = sum(
            t.total_value for t in purchases if t.total_value
        ) or Decimal("0")
        sale_value = sum(
            t.total_value for t in sales if t.total_value
        ) or Decimal("0")

        return {
            "total_transactions": len(transactions),
            "purchases": len(purchases),
            "sales": len(sales),
            "total_purchase_value": purchase_value,
            "total_sale_value": sale_value,
            "unique_insiders": len(insiders),
            "unique_companies": len(companies),
            "net_direction": "buying" if purchase_value > sale_value else "selling",
        }
