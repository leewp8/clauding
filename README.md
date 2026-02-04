# Insider Trading Tracker

Monitor SEC Form 4 filings for insider buying and selling activity. Track companies in your watchlist and portfolio, and get alerts when significant insider transactions occur.

## Features

- **SEC Form 4 Monitoring**: Fetches and parses Form 4 filings directly from SEC EDGAR
- **Watchlist Management**: Track any publicly traded company by ticker symbol
- **Portfolio Tracking**: Monitor insider activity specifically for your holdings
- **Significance Detection**: AI-powered analysis to identify meaningful transactions
- **Cluster Detection**: Identify coordinated insider activity (multiple insiders buying/selling)
- **Alerting System**: Get notified about significant insider transactions
- **Rich CLI**: Beautiful command-line interface with tables and formatting

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd insider-trading-tracker

# Install with pip
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt
```

## Quick Start

```bash
# Add companies to your watchlist
insider-tracker watchlist add AAPL
insider-tracker watchlist add MSFT
insider-tracker watchlist add GOOGL

# Add holdings to your portfolio
insider-tracker portfolio add NVDA --shares 100 --cost 450.00

# Scan for insider activity
insider-tracker scan

# Look up a specific company
insider-tracker lookup TSLA --days 90

# Check your alerts
insider-tracker alerts list
```

## CLI Commands

### Status

```bash
# Show tracker status
insider-tracker status
```

### Watchlist Management

```bash
# Add a ticker to watchlist
insider-tracker watchlist add TICKER

# Remove a ticker
insider-tracker watchlist remove TICKER

# List all watchlist entries
insider-tracker watchlist list

# Bulk import tickers
insider-tracker watchlist import AAPL MSFT GOOGL AMZN
```

### Portfolio Management

```bash
# Add a portfolio holding
insider-tracker portfolio add TICKER --shares 100 --cost 50.00

# List portfolio holdings
insider-tracker portfolio list

# Analyze insider exposure for your portfolio
insider-tracker portfolio exposure
```

### Scanning & Lookup

```bash
# Scan all watchlist companies for insider activity
insider-tracker scan --days 7 --significance medium

# Look up a specific ticker
insider-tracker lookup AAPL --days 90
```

### Alerts

```bash
# List recent alerts
insider-tracker alerts list

# Show only unread alerts
insider-tracker alerts list --unread

# Filter by ticker
insider-tracker alerts list --ticker AAPL

# Mark alert as read
insider-tracker alerts read ALERT_ID

# Mark all alerts as read
insider-tracker alerts read --all

# Dismiss an alert
insider-tracker alerts dismiss ALERT_ID

# Clear old alerts
insider-tracker alerts clear --days 30
```

## Significance Levels

Transactions are analyzed and assigned a significance level:

| Level | Description |
|-------|-------------|
| **LOW** | Routine transactions, small values, non-executive |
| **MEDIUM** | Notable activity worth monitoring |
| **HIGH** | Significant transaction, executive involvement |
| **CRITICAL** | Major transaction, CEO/CFO, very large value |

### What Makes a Transaction Significant?

- **Insider Role**: CEO/CFO transactions weighted more heavily than other officers
- **Transaction Type**: Open market purchases/sales more significant than option exercises
- **Transaction Value**: Larger dollar amounts increase significance
- **Direction**: Purchases are generally more significant (insiders always have reasons to sell)
- **Ownership Change**: Large percentage changes in ownership stake
- **Cluster Activity**: Multiple insiders transacting in same direction

## Data Storage

All data is stored locally in `~/.insider-tracker/`:

- `watchlist.json` - Your watchlist and portfolio
- `alerts.json` - Alert history
- `seen_transactions.json` - Processed transaction IDs (deduplication)
- `config.json` - Configuration settings

## Configuration

Edit `~/.insider-tracker/config.json` to customize:

```json
{
  "user_agent": "YourApp/1.0 (your-email@example.com)",
  "scan_days": 7,
  "min_significance": "medium",
  "thresholds": {
    "min_transaction_value": "10000",
    "large_transaction_value": "100000",
    "significant_transaction_value": "500000",
    "critical_transaction_value": "1000000",
    "ownership_change_percent": "10",
    "cluster_window_days": 7,
    "cluster_min_insiders": 3
  }
}
```

## Python API

```python
from insider_tracker import InsiderTracker

# Initialize tracker
tracker = InsiderTracker()

# Add to watchlist
tracker.add_to_watchlist("AAPL")

# Scan for activity
alerts = tracker.scan_watchlist(days=7)

# Get ticker summary
summary = tracker.get_ticker_summary("AAPL", days=90)
print(f"Purchases: {summary['stats']['purchases']}")
print(f"Sales: {summary['stats']['sales']}")

# Check portfolio exposure
exposure = tracker.get_portfolio_exposure()
print(f"Net sentiment: {exposure['net_insider_sentiment']}")
```

## SEC EDGAR API

This tool uses the SEC EDGAR API to fetch Form 4 filings. The SEC requires:

1. A User-Agent header with contact information
2. Rate limiting to 10 requests per second

Please update the `user_agent` in configuration with your actual contact email.

## Form 4 Transaction Codes

| Code | Description |
|------|-------------|
| P | Open market or private purchase |
| S | Open market or private sale |
| A | Grant, award, or other acquisition |
| M | Exercise or conversion of derivative |
| G | Gift |
| F | Payment of exercise price or tax liability |

## Disclaimer

This tool is for informational purposes only. Insider trading data should be one of many factors in investment decisions. Always do your own research and consult with financial professionals.

## License

MIT License
