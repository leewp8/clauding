"""Watchlist and portfolio management for insider trading tracking."""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from insider_tracker.models import WatchlistEntry
from insider_tracker.sec_client import SECClient


class WatchlistManager:
    """Manages watchlist and portfolio of tracked companies."""

    DEFAULT_DATA_DIR = Path.home() / ".insider-tracker"
    WATCHLIST_FILE = "watchlist.json"

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        sec_client: Optional[SECClient] = None,
    ):
        """Initialize watchlist manager.

        Args:
            data_dir: Directory to store watchlist data
            sec_client: SEC client for ticker lookups
        """
        self.data_dir = data_dir or self.DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.watchlist_path = self.data_dir / self.WATCHLIST_FILE
        self.sec_client = sec_client or SECClient()
        self._entries: dict[str, WatchlistEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load watchlist from disk."""
        if self.watchlist_path.exists():
            try:
                with open(self.watchlist_path, "r") as f:
                    data = json.load(f)
                    for ticker, entry_data in data.items():
                        # Handle Decimal fields
                        if entry_data.get("shares_owned"):
                            entry_data["shares_owned"] = Decimal(str(entry_data["shares_owned"]))
                        if entry_data.get("average_cost"):
                            entry_data["average_cost"] = Decimal(str(entry_data["average_cost"]))
                        # Handle datetime
                        if entry_data.get("added_date"):
                            entry_data["added_date"] = datetime.fromisoformat(
                                entry_data["added_date"]
                            )
                        self._entries[ticker.upper()] = WatchlistEntry(**entry_data)
            except Exception as e:
                print(f"Error loading watchlist: {e}")
                self._entries = {}

    def _save(self) -> None:
        """Save watchlist to disk."""
        try:
            data = {}
            for ticker, entry in self._entries.items():
                entry_dict = entry.model_dump()
                # Convert Decimal to str for JSON
                if entry_dict.get("shares_owned"):
                    entry_dict["shares_owned"] = str(entry_dict["shares_owned"])
                if entry_dict.get("average_cost"):
                    entry_dict["average_cost"] = str(entry_dict["average_cost"])
                # Convert datetime to ISO format
                if entry_dict.get("added_date"):
                    entry_dict["added_date"] = entry_dict["added_date"].isoformat()
                data[ticker] = entry_dict

            with open(self.watchlist_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving watchlist: {e}")

    def add(
        self,
        ticker: str,
        is_portfolio: bool = False,
        shares_owned: Optional[Decimal] = None,
        average_cost: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> WatchlistEntry:
        """Add a ticker to the watchlist.

        Args:
            ticker: Stock ticker symbol
            is_portfolio: Whether this is a portfolio holding
            shares_owned: Number of shares owned (for portfolio)
            average_cost: Average cost basis (for portfolio)
            notes: User notes

        Returns:
            The created watchlist entry
        """
        ticker = ticker.upper().strip()

        # Look up company info
        cik = self.sec_client.ticker_to_cik(ticker)
        company_name = None
        if cik:
            company = self.sec_client.get_company_info(cik)
            if company:
                company_name = company.name

        entry = WatchlistEntry(
            ticker=ticker,
            cik=cik,
            company_name=company_name,
            added_date=datetime.now(),
            notes=notes,
            is_portfolio=is_portfolio,
            shares_owned=shares_owned,
            average_cost=average_cost,
        )

        self._entries[ticker] = entry
        self._save()
        return entry

    def remove(self, ticker: str) -> bool:
        """Remove a ticker from the watchlist.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if removed, False if not found
        """
        ticker = ticker.upper().strip()
        if ticker in self._entries:
            del self._entries[ticker]
            self._save()
            return True
        return False

    def get(self, ticker: str) -> Optional[WatchlistEntry]:
        """Get a watchlist entry by ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            WatchlistEntry or None
        """
        return self._entries.get(ticker.upper().strip())

    def get_all(self) -> list[WatchlistEntry]:
        """Get all watchlist entries.

        Returns:
            List of all watchlist entries
        """
        return list(self._entries.values())

    def get_watchlist(self) -> list[WatchlistEntry]:
        """Get only watchlist entries (not portfolio).

        Returns:
            List of watchlist entries
        """
        return [e for e in self._entries.values() if not e.is_portfolio]

    def get_portfolio(self) -> list[WatchlistEntry]:
        """Get only portfolio entries.

        Returns:
            List of portfolio entries
        """
        return [e for e in self._entries.values() if e.is_portfolio]

    def get_tickers(self) -> list[str]:
        """Get all tracked ticker symbols.

        Returns:
            List of ticker symbols
        """
        return list(self._entries.keys())

    def get_ciks(self) -> list[str]:
        """Get all tracked CIKs.

        Returns:
            List of CIKs (excluding None values)
        """
        return [e.cik for e in self._entries.values() if e.cik]

    def update(
        self,
        ticker: str,
        is_portfolio: Optional[bool] = None,
        shares_owned: Optional[Decimal] = None,
        average_cost: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> Optional[WatchlistEntry]:
        """Update a watchlist entry.

        Args:
            ticker: Stock ticker symbol
            is_portfolio: Whether this is a portfolio holding
            shares_owned: Number of shares owned
            average_cost: Average cost basis
            notes: User notes

        Returns:
            Updated entry or None if not found
        """
        ticker = ticker.upper().strip()
        entry = self._entries.get(ticker)
        if not entry:
            return None

        if is_portfolio is not None:
            entry.is_portfolio = is_portfolio
        if shares_owned is not None:
            entry.shares_owned = shares_owned
        if average_cost is not None:
            entry.average_cost = average_cost
        if notes is not None:
            entry.notes = notes

        self._entries[ticker] = entry
        self._save()
        return entry

    def move_to_portfolio(
        self,
        ticker: str,
        shares_owned: Decimal,
        average_cost: Optional[Decimal] = None,
    ) -> Optional[WatchlistEntry]:
        """Move a watchlist entry to portfolio.

        Args:
            ticker: Stock ticker symbol
            shares_owned: Number of shares owned
            average_cost: Average cost basis

        Returns:
            Updated entry or None if not found
        """
        return self.update(
            ticker,
            is_portfolio=True,
            shares_owned=shares_owned,
            average_cost=average_cost,
        )

    def move_to_watchlist(self, ticker: str) -> Optional[WatchlistEntry]:
        """Move a portfolio entry back to watchlist.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Updated entry or None if not found
        """
        return self.update(
            ticker,
            is_portfolio=False,
            shares_owned=None,
            average_cost=None,
        )

    def contains(self, ticker: str) -> bool:
        """Check if a ticker is in the watchlist.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if in watchlist
        """
        return ticker.upper().strip() in self._entries

    def count(self) -> int:
        """Get total number of entries.

        Returns:
            Number of entries
        """
        return len(self._entries)

    def clear(self) -> None:
        """Clear all entries from the watchlist."""
        self._entries = {}
        self._save()

    def import_tickers(
        self,
        tickers: list[str],
        is_portfolio: bool = False,
    ) -> list[WatchlistEntry]:
        """Bulk import multiple tickers.

        Args:
            tickers: List of ticker symbols
            is_portfolio: Whether these are portfolio holdings

        Returns:
            List of created entries
        """
        entries = []
        for ticker in tickers:
            ticker = ticker.upper().strip()
            if ticker and ticker not in self._entries:
                entry = self.add(ticker, is_portfolio=is_portfolio)
                entries.append(entry)
        return entries

    def export_tickers(self) -> dict[str, list[str]]:
        """Export tickers as a dictionary.

        Returns:
            Dictionary with 'watchlist' and 'portfolio' keys
        """
        return {
            "watchlist": [e.ticker for e in self.get_watchlist()],
            "portfolio": [e.ticker for e in self.get_portfolio()],
        }
