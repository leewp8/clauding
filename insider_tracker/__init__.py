"""
Insider Trading Tracker - Monitor SEC Form 4 filings for insider trading activity.

This tool tracks insider buying and selling for companies in your watchlist
and portfolio, alerting you to significant transactions.
"""

__version__ = "1.0.0"
__author__ = "Insider Trading Tracker"

from insider_tracker.models import (
    InsiderTransaction,
    InsiderInfo,
    Company,
    TransactionType,
    SignificanceLevel,
)
from insider_tracker.sec_client import SECClient
from insider_tracker.watchlist import WatchlistManager
from insider_tracker.alerts import AlertManager, Alert
from insider_tracker.tracker import InsiderTracker
from insider_tracker.dashboard import DashboardGenerator
from insider_tracker.price_client import PriceClient, StockQuote
from insider_tracker.news_client import NewsClient, NewsArticle

__all__ = [
    "InsiderTransaction",
    "InsiderInfo",
    "Company",
    "TransactionType",
    "SignificanceLevel",
    "SECClient",
    "WatchlistManager",
    "AlertManager",
    "Alert",
    "InsiderTracker",
    "DashboardGenerator",
    "PriceClient",
    "StockQuote",
    "NewsClient",
    "NewsArticle",
]
