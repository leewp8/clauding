"""News fetching via NewsAPI.org."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import requests


@dataclass
class NewsArticle:
    """A single news article."""

    title: str
    description: Optional[str]
    url: str
    source: str
    published_at: Optional[datetime]


class NewsClient:
    """Fetches news from NewsAPI.org."""

    BASE_URL = "https://newsapi.org/v2"

    def __init__(self, api_key: str):
        """Initialize with NewsAPI key.

        Args:
            api_key: NewsAPI.org API key
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers["X-Api-Key"] = api_key

    def get_company_news(
        self,
        query: str,
        days: int = 2,
        max_results: int = 5,
    ) -> list[NewsArticle]:
        """Fetch recent news articles for a company/ticker.

        Uses the /v2/everything endpoint with query parameter.

        Args:
            query: Search query (ticker or company name)
            days: How many days back to search
            max_results: Maximum number of articles to return

        Returns:
            List of NewsArticle objects
        """
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        try:
            response = self.session.get(
                f"{self.BASE_URL}/everything",
                params={
                    "q": query,
                    "from": from_date,
                    "sortBy": "relevancy",
                    "language": "en",
                    "pageSize": max_results,
                },
                timeout=10,
            )

            if response.status_code == 401:
                print("NewsAPI: Invalid API key")
                return []
            if response.status_code == 429:
                print("NewsAPI: Rate limit exceeded")
                return []
            if response.status_code != 200:
                return []

            data = response.json()
            articles = []

            for item in data.get("articles", [])[:max_results]:
                published_at = None
                if item.get("publishedAt"):
                    try:
                        published_at = datetime.fromisoformat(
                            item["publishedAt"].replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                articles.append(
                    NewsArticle(
                        title=item.get("title", ""),
                        description=item.get("description"),
                        url=item.get("url", ""),
                        source=item.get("source", {}).get("name", "Unknown"),
                        published_at=published_at,
                    )
                )

            return articles

        except requests.RequestException:
            return []

    def get_news_for_tickers(
        self,
        ticker_names: dict[str, str],
        days: int = 2,
        max_per_ticker: int = 5,
    ) -> dict[str, list[NewsArticle]]:
        """Fetch news for multiple tickers.

        Args:
            ticker_names: Dict mapping ticker -> company name
            days: How many days back
            max_per_ticker: Max articles per ticker

        Returns:
            Dict mapping ticker -> list of NewsArticle
        """
        results = {}

        for ticker, company_name in ticker_names.items():
            # Search by company name if available, otherwise ticker
            query = f'"{company_name}" OR "{ticker}"' if company_name else ticker
            articles = self.get_company_news(
                query=query,
                days=days,
                max_results=max_per_ticker,
            )
            results[ticker] = articles

        return results
