"""Stock price fetching via yfinance."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import yfinance as yf


@dataclass
class StockQuote:
    """Price data for a single stock."""

    ticker: str
    current_price: Decimal
    previous_close: Decimal
    daily_change: Decimal
    daily_change_percent: float
    currency: str

    @property
    def is_positive(self) -> bool:
        """Check if the daily change is positive."""
        return self.daily_change >= 0


class PriceClient:
    """Fetches stock quotes using yfinance."""

    def get_quote(self, ticker: str) -> Optional[StockQuote]:
        """Get current quote for a single ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            StockQuote or None if fetch fails
        """
        quotes = self.get_quotes([ticker])
        return quotes.get(ticker)

    def get_quotes(self, tickers: list[str]) -> dict[str, StockQuote]:
        """Get quotes for multiple tickers in a single batch call.

        Uses yf.download with period="2d" for efficiency, then
        supplements with individual ticker info for intraday data.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> StockQuote (missing tickers omitted)
        """
        if not tickers:
            return {}

        quotes = {}

        # Try batch download for last 2 trading days
        try:
            data = yf.download(tickers, period="5d", progress=False, threads=True)
        except Exception:
            data = None

        for ticker in tickers:
            try:
                quote = self._build_quote_from_ticker(ticker, data)
                if quote:
                    quotes[ticker] = quote
            except Exception:
                continue

        return quotes

    def _build_quote_from_ticker(
        self,
        ticker: str,
        batch_data,
    ) -> Optional[StockQuote]:
        """Build a StockQuote from yfinance data.

        Tries batch data first, falls back to individual ticker info.

        Args:
            ticker: Stock ticker symbol
            batch_data: DataFrame from yf.download (may be None)

        Returns:
            StockQuote or None
        """
        current_price = None
        previous_close = None
        currency = "USD"

        # Try to get data from the individual ticker for most current info
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            current_price = Decimal(str(info.last_price))
            previous_close = Decimal(str(info.previous_close))
            currency = getattr(info, "currency", "USD") or "USD"
        except Exception:
            pass

        # Fall back to batch data if individual ticker info failed
        if (current_price is None or previous_close is None) and batch_data is not None:
            try:
                if len([t for t in [ticker] if t in (batch_data.columns.get_level_values(1) if batch_data.columns.nlevels > 1 else [])]) > 0:
                    # Multi-ticker DataFrame
                    closes = batch_data["Close"][ticker].dropna()
                else:
                    # Single-ticker DataFrame
                    closes = batch_data["Close"].dropna()

                if len(closes) >= 2:
                    current_price = current_price or Decimal(str(round(float(closes.iloc[-1]), 4)))
                    previous_close = previous_close or Decimal(str(round(float(closes.iloc[-2]), 4)))
                elif len(closes) == 1:
                    current_price = current_price or Decimal(str(round(float(closes.iloc[-1]), 4)))
            except Exception:
                pass

        if current_price is None or previous_close is None:
            return None

        daily_change = current_price - previous_close
        if previous_close != 0:
            daily_change_percent = float(daily_change / previous_close * 100)
        else:
            daily_change_percent = 0.0

        return StockQuote(
            ticker=ticker,
            current_price=current_price,
            previous_close=previous_close,
            daily_change=daily_change,
            daily_change_percent=round(daily_change_percent, 2),
            currency=currency,
        )
