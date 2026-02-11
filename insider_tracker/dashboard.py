"""Dashboard generation for stock portfolio."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from insider_tracker.config import Config
from insider_tracker.models import WatchlistEntry
from insider_tracker.news_client import NewsArticle, NewsClient
from insider_tracker.price_client import PriceClient, StockQuote
from insider_tracker.sec_client import SECClient
from insider_tracker.watchlist import WatchlistManager


@dataclass
class DashboardStock:
    """All data for a single stock in the dashboard."""

    ticker: str
    company_name: Optional[str]
    is_portfolio: bool
    shares_owned: Optional[Decimal]
    average_cost: Optional[Decimal]

    # Price data
    quote: Optional[StockQuote] = None

    # Computed portfolio values (only for portfolio entries)
    market_value: Optional[Decimal] = None
    cost_basis_total: Optional[Decimal] = None
    unrealized_gain: Optional[Decimal] = None
    unrealized_gain_percent: Optional[float] = None

    # Big mover data (only populated if >= threshold)
    is_big_mover: bool = False
    news: list[NewsArticle] = field(default_factory=list)
    insider_summary: Optional[str] = None
    recent_insider_transactions: list[dict] = field(default_factory=list)


@dataclass
class DashboardData:
    """Complete data for rendering the dashboard."""

    generated_at: datetime
    big_mover_threshold: float
    portfolio_stocks: list[DashboardStock]
    watchlist_stocks: list[DashboardStock]

    # Portfolio totals
    total_market_value: Decimal
    total_cost_basis: Decimal
    total_unrealized_gain: Decimal
    total_daily_change: Decimal


class DashboardGenerator:
    """Generates the stock portfolio dashboard."""

    DEFAULT_OUTPUT = "dashboard.html"
    DEFAULT_THRESHOLD = 5.0

    def __init__(
        self,
        config: Config,
        watchlist: WatchlistManager,
        sec_client: SECClient,
    ):
        """Initialize dashboard generator.

        Args:
            config: Application configuration
            watchlist: Watchlist manager for portfolio/watchlist data
            sec_client: SEC client for insider data
        """
        self.config = config
        self.watchlist = watchlist
        self.sec_client = sec_client
        self.price_client = PriceClient()
        self.news_client = self._create_news_client()

    def _create_news_client(self) -> Optional[NewsClient]:
        """Create news client if API key is configured."""
        api_key = self.config.newsapi_key
        if api_key:
            return NewsClient(api_key)
        return None

    def generate(
        self,
        output_path: Optional[Path] = None,
        threshold: Optional[float] = None,
    ) -> Path:
        """Generate the dashboard HTML file.

        Args:
            output_path: Where to write the HTML file
            threshold: Big mover threshold percentage (overrides config)

        Returns:
            Path to the generated HTML file
        """
        # Determine output path
        if output_path is None:
            configured = self.config.dashboard_output_path
            if configured:
                output_path = Path(configured)
            else:
                output_path = self.config.data_dir / self.DEFAULT_OUTPUT

        # Determine threshold
        if threshold is None:
            threshold = self.config.big_mover_threshold

        # Gather all data
        data = self._gather_data(threshold)

        # Render HTML
        from insider_tracker.dashboard_html import render_dashboard_html

        html = render_dashboard_html(data)

        # Write to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        return output_path

    def _gather_data(self, threshold: float) -> DashboardData:
        """Gather all data for the dashboard.

        Args:
            threshold: Big mover threshold percentage

        Returns:
            Complete DashboardData for rendering
        """
        portfolio_entries = self.watchlist.get_portfolio()
        watchlist_entries = self.watchlist.get_watchlist()
        all_entries = portfolio_entries + watchlist_entries

        # Batch-fetch prices for all tickers
        tickers = [e.ticker for e in all_entries]
        quotes = self.price_client.get_quotes(tickers) if tickers else {}

        # Build stock objects
        portfolio_stocks = []
        watchlist_stocks = []

        for entry in all_entries:
            quote = quotes.get(entry.ticker)
            stock = self._build_stock(entry, quote, threshold)

            if entry.is_portfolio:
                portfolio_stocks.append(stock)
            else:
                watchlist_stocks.append(stock)

        # Fetch news and insider data for big movers
        big_movers = [s for s in portfolio_stocks + watchlist_stocks if s.is_big_mover]
        self._enrich_big_movers(big_movers, all_entries)

        # Compute portfolio totals
        total_market_value = sum(
            (s.market_value for s in portfolio_stocks if s.market_value is not None),
            Decimal("0"),
        )
        total_cost_basis = sum(
            (s.cost_basis_total for s in portfolio_stocks if s.cost_basis_total is not None),
            Decimal("0"),
        )
        total_unrealized_gain = total_market_value - total_cost_basis
        total_daily_change = sum(
            (
                s.quote.daily_change * s.shares_owned
                for s in portfolio_stocks
                if s.quote and s.shares_owned
            ),
            Decimal("0"),
        )

        return DashboardData(
            generated_at=datetime.now(),
            big_mover_threshold=threshold,
            portfolio_stocks=portfolio_stocks,
            watchlist_stocks=watchlist_stocks,
            total_market_value=total_market_value,
            total_cost_basis=total_cost_basis,
            total_unrealized_gain=total_unrealized_gain,
            total_daily_change=total_daily_change,
        )

    def _build_stock(
        self,
        entry: WatchlistEntry,
        quote: Optional[StockQuote],
        threshold: float,
    ) -> DashboardStock:
        """Build a DashboardStock from a watchlist entry and quote.

        Args:
            entry: Watchlist/portfolio entry
            quote: Stock quote (may be None)
            threshold: Big mover threshold percentage

        Returns:
            DashboardStock object
        """
        stock = DashboardStock(
            ticker=entry.ticker,
            company_name=entry.company_name,
            is_portfolio=entry.is_portfolio,
            shares_owned=entry.shares_owned,
            average_cost=entry.average_cost,
            quote=quote,
        )

        # Compute portfolio values
        if entry.is_portfolio and quote and entry.shares_owned:
            stock.market_value = quote.current_price * entry.shares_owned
            if entry.average_cost:
                stock.cost_basis_total = entry.average_cost * entry.shares_owned
                stock.unrealized_gain = stock.market_value - stock.cost_basis_total
                if stock.cost_basis_total != 0:
                    stock.unrealized_gain_percent = float(
                        stock.unrealized_gain / stock.cost_basis_total * 100
                    )

        # Check if big mover
        if quote and abs(quote.daily_change_percent) >= threshold:
            stock.is_big_mover = True

        return stock

    def _enrich_big_movers(
        self,
        big_movers: list[DashboardStock],
        all_entries: list[WatchlistEntry],
    ) -> None:
        """Fetch news and insider data for big movers.

        Args:
            big_movers: List of stocks with large daily moves
            all_entries: All watchlist entries (for CIK lookup)
        """
        if not big_movers:
            return

        # Build ticker -> company name mapping for news queries
        entry_map = {e.ticker: e for e in all_entries}

        # Fetch news if client is available
        if self.news_client:
            ticker_names = {
                s.ticker: s.company_name or s.ticker for s in big_movers
            }
            news_map = self.news_client.get_news_for_tickers(ticker_names)
            for stock in big_movers:
                stock.news = news_map.get(stock.ticker, [])

        # Fetch insider activity for each big mover
        lookback_days = int(self.config.get("dashboard.insider_lookback_days", 30))
        for stock in big_movers:
            entry = entry_map.get(stock.ticker)
            cik = entry.cik if entry else None
            summary, transactions = self._fetch_insider_summary(
                stock.ticker, cik, lookback_days
            )
            stock.insider_summary = summary
            stock.recent_insider_transactions = transactions

    def _fetch_insider_summary(
        self,
        ticker: str,
        cik: Optional[str],
        days: int = 30,
    ) -> tuple[Optional[str], list[dict]]:
        """Fetch recent insider activity summary for a big mover.

        Args:
            ticker: Stock ticker symbol
            cik: Company CIK (if known)
            days: Lookback period in days

        Returns:
            Tuple of (summary_text, list_of_recent_transactions)
        """
        try:
            transactions = self.sec_client.get_recent_form4_filings(
                cik=cik,
                ticker=ticker if not cik else None,
                days=days,
                limit=20,
            )
        except Exception:
            return "Insider data unavailable", []

        if not transactions:
            return None, []

        # Build summary
        purchases = [t for t in transactions if t.is_purchase]
        sales = [t for t in transactions if t.is_sale]

        total_bought = sum(t.total_value or Decimal("0") for t in purchases)
        total_sold = sum(t.total_value or Decimal("0") for t in sales)

        parts = []
        if purchases:
            parts.append(
                f"{len(purchases)} insider{'s' if len(purchases) > 1 else ''} "
                f"bought ${total_bought:,.0f}"
            )
        if sales:
            parts.append(
                f"{len(sales)} insider{'s' if len(sales) > 1 else ''} "
                f"sold ${total_sold:,.0f}"
            )

        summary = f"Last {days} days: " + "; ".join(parts) if parts else None

        # Build transaction list for display
        transaction_dicts = []
        for t in transactions[:5]:
            action = "Bought" if t.is_purchase else "Sold" if t.is_sale else "Transacted"
            date_str = (
                t.transaction_date.strftime("%Y-%m-%d")
                if t.transaction_date
                else "N/A"
            )
            transaction_dicts.append(
                {
                    "insider": t.insider.name,
                    "title": t.insider.officer_title or "",
                    "action": action,
                    "shares": f"{t.shares:,.0f}",
                    "value": f"${t.total_value:,.0f}" if t.total_value else "N/A",
                    "date": date_str,
                }
            )

        return summary, transaction_dicts
