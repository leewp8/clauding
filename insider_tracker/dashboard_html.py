"""HTML template and rendering for the stock portfolio dashboard."""

import html
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from insider_tracker.dashboard import DashboardData, DashboardStock


def render_dashboard_html(data: "DashboardData") -> str:
    """Render a DashboardData object to a self-contained HTML string.

    Args:
        data: Complete dashboard data

    Returns:
        Self-contained HTML string
    """
    timestamp = data.generated_at.strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portfolio Dashboard - {timestamp}</title>
    <style>
{_get_css()}
    </style>
</head>
<body>
    {_render_header(data)}
    {_render_portfolio_summary(data)}
    {_render_big_movers(data)}
    {_render_portfolio_table(data)}
    {_render_watchlist_table(data)}
    {_render_footer(data)}
    <script>
{_get_js()}
    </script>
</body>
</html>"""


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return html.escape(str(text)) if text else ""


def _format_currency(value: Decimal) -> str:
    """Format a Decimal as currency."""
    return f"${value:,.2f}"


def _format_percent(value: float) -> str:
    """Format a float as percentage."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def _change_class(value) -> str:
    """Return CSS class for positive/negative values."""
    if isinstance(value, float):
        return "positive" if value >= 0 else "negative"
    return "positive" if value >= 0 else "negative"


def _get_css() -> str:
    """Return all CSS as a single string."""
    return """
        :root {
            --bg: #0f1117;
            --surface: #1a1d27;
            --surface2: #242836;
            --border: #2e3345;
            --text: #e1e4ed;
            --text-dim: #8b90a0;
            --green: #00c853;
            --green-bg: rgba(0, 200, 83, 0.1);
            --red: #ff1744;
            --red-bg: rgba(255, 23, 68, 0.1);
            --blue: #448aff;
            --yellow: #ffd600;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 24px;
        }

        .container { max-width: 1200px; margin: 0 auto; }

        h1 {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 4px;
        }

        h2 {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--text);
        }

        .header {
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }

        .header .timestamp {
            color: var(--text-dim);
            font-size: 14px;
        }

        /* Summary Cards */
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }

        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
        }

        .card .label {
            font-size: 13px;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .card .value {
            font-size: 28px;
            font-weight: 700;
        }

        .card .sub {
            font-size: 14px;
            margin-top: 4px;
        }

        /* Tables */
        .table-section {
            margin-bottom: 32px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border-radius: 8px;
            overflow: hidden;
        }

        th {
            text-align: left;
            padding: 12px 16px;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-dim);
            background: var(--surface2);
            border-bottom: 1px solid var(--border);
        }

        th.right, td.right { text-align: right; }

        td {
            padding: 12px 16px;
            font-size: 14px;
            border-bottom: 1px solid var(--border);
        }

        tr:last-child td { border-bottom: none; }

        tr:hover { background: var(--surface2); }

        .ticker {
            font-weight: 600;
            color: var(--blue);
        }

        .positive { color: var(--green); }
        .negative { color: var(--red); }

        /* Big Movers */
        .big-movers {
            margin-bottom: 32px;
        }

        .mover-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 12px;
            overflow: hidden;
        }

        .mover-header {
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }

        .mover-header:hover { background: var(--surface2); }

        .mover-header .left {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .mover-header .ticker { font-size: 16px; }

        .mover-header .change {
            font-size: 20px;
            font-weight: 700;
        }

        .mover-details {
            padding: 0 20px 20px;
            border-top: 1px solid var(--border);
        }

        .mover-details h3 {
            font-size: 14px;
            color: var(--text-dim);
            margin: 16px 0 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .news-list {
            list-style: none;
        }

        .news-list li {
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
        }

        .news-list li:last-child { border-bottom: none; }

        .news-list a {
            color: var(--text);
            text-decoration: none;
        }

        .news-list a:hover { color: var(--blue); }

        .news-list .source {
            font-size: 12px;
            color: var(--text-dim);
            margin-top: 2px;
        }

        .insider-table {
            font-size: 13px;
        }

        .insider-table td {
            padding: 8px 12px;
        }

        .note {
            color: var(--text-dim);
            font-size: 14px;
            font-style: italic;
            padding: 12px 0;
        }

        .empty-state {
            text-align: center;
            padding: 48px 24px;
            color: var(--text-dim);
        }

        .footer {
            text-align: center;
            color: var(--text-dim);
            font-size: 12px;
            padding: 24px 0;
            border-top: 1px solid var(--border);
        }

        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }

        .badge.up { background: var(--green-bg); color: var(--green); }
        .badge.down { background: var(--red-bg); color: var(--red); }
    """


def _get_js() -> str:
    """Return minimal JS for interactivity."""
    return """
        document.querySelectorAll('.mover-header').forEach(header => {
            header.addEventListener('click', () => {
                const details = header.nextElementSibling;
                if (details) {
                    details.style.display = details.style.display === 'none' ? 'block' : 'none';
                }
            });
        });
    """


def _render_header(data: "DashboardData") -> str:
    """Render the page header."""
    timestamp = data.generated_at.strftime("%B %d, %Y at %I:%M %p")
    total = len(data.portfolio_stocks) + len(data.watchlist_stocks)
    return f"""
    <div class="container">
    <div class="header">
        <h1>Portfolio Dashboard</h1>
        <div class="timestamp">Generated {_esc(timestamp)} &mdash; {total} stocks tracked</div>
    </div>"""


def _render_portfolio_summary(data: "DashboardData") -> str:
    """Render the portfolio summary cards."""
    if not data.portfolio_stocks:
        return ""

    gain_class = _change_class(float(data.total_unrealized_gain))
    daily_class = _change_class(float(data.total_daily_change))
    gain_pct = (
        float(data.total_unrealized_gain / data.total_cost_basis * 100)
        if data.total_cost_basis != 0
        else 0.0
    )

    return f"""
    <div class="summary-cards">
        <div class="card">
            <div class="label">Market Value</div>
            <div class="value">{_format_currency(data.total_market_value)}</div>
            <div class="sub">{len(data.portfolio_stocks)} holdings</div>
        </div>
        <div class="card">
            <div class="label">Cost Basis</div>
            <div class="value">{_format_currency(data.total_cost_basis)}</div>
        </div>
        <div class="card">
            <div class="label">Unrealized P&amp;L</div>
            <div class="value {gain_class}">{_format_currency(data.total_unrealized_gain)}</div>
            <div class="sub {gain_class}">{_format_percent(gain_pct)}</div>
        </div>
        <div class="card">
            <div class="label">Today's Change</div>
            <div class="value {daily_class}">{_format_currency(data.total_daily_change)}</div>
        </div>
    </div>"""


def _render_big_movers(data: "DashboardData") -> str:
    """Render the big movers section."""
    all_stocks = data.portfolio_stocks + data.watchlist_stocks
    movers = [s for s in all_stocks if s.is_big_mover]

    if not movers:
        return ""

    cards = []
    for stock in sorted(movers, key=lambda s: abs(s.quote.daily_change_percent), reverse=True):
        cards.append(_render_mover_card(stock))

    return f"""
    <div class="big-movers">
        <h2>Big Movers (>{data.big_mover_threshold:.0f}%)</h2>
        {"".join(cards)}
    </div>"""


def _render_mover_card(stock: "DashboardStock") -> str:
    """Render a single big mover card."""
    q = stock.quote
    change_class = _change_class(q.daily_change_percent)
    badge_class = "up" if q.daily_change_percent >= 0 else "down"
    arrow = "&#9650;" if q.daily_change_percent >= 0 else "&#9660;"
    company = _esc(stock.company_name) if stock.company_name else ""

    # News section
    news_html = ""
    if stock.news:
        items = []
        for article in stock.news:
            source = _esc(article.source)
            title = _esc(article.title)
            url = _esc(article.url)
            date = (
                article.published_at.strftime("%b %d")
                if article.published_at
                else ""
            )
            items.append(
                f'<li><a href="{url}" target="_blank">{title}</a>'
                f'<div class="source">{source} {date}</div></li>'
            )
        news_html = f"""
            <h3>Recent News</h3>
            <ul class="news-list">{"".join(items)}</ul>"""
    elif stock.is_big_mover:
        news_html = '<p class="note">Configure NewsAPI key to see news headlines</p>'

    # Insider section
    insider_html = ""
    if stock.insider_summary:
        insider_html = f'<h3>Insider Activity</h3><p>{_esc(stock.insider_summary)}</p>'

        if stock.recent_insider_transactions:
            rows = []
            for t in stock.recent_insider_transactions:
                rows.append(
                    f"<tr><td>{_esc(t['date'])}</td><td>{_esc(t['insider'])}</td>"
                    f"<td>{_esc(t['action'])}</td><td class='right'>{_esc(t['shares'])}</td>"
                    f"<td class='right'>{_esc(t['value'])}</td></tr>"
                )
            insider_html += f"""
            <table class="insider-table">
                <thead><tr><th>Date</th><th>Insider</th><th>Action</th>
                <th class="right">Shares</th><th class="right">Value</th></tr></thead>
                <tbody>{"".join(rows)}</tbody>
            </table>"""

    return f"""
        <div class="mover-card">
            <div class="mover-header">
                <div class="left">
                    <span class="ticker">{_esc(stock.ticker)}</span>
                    <span>{company}</span>
                    <span>{_format_currency(q.current_price)}</span>
                </div>
                <div>
                    <span class="change {change_class}">
                        {arrow} {_format_percent(q.daily_change_percent)}
                    </span>
                    <span class="badge {badge_class}">
                        {_format_currency(q.daily_change)}
                    </span>
                </div>
            </div>
            <div class="mover-details">
                {news_html}
                {insider_html}
            </div>
        </div>"""


def _render_portfolio_table(data: "DashboardData") -> str:
    """Render the portfolio holdings table."""
    if not data.portfolio_stocks:
        return """
    <div class="table-section">
        <h2>Portfolio</h2>
        <div class="empty-state">
            No portfolio holdings. Add some with: insider-tracker portfolio add TICKER -s SHARES
        </div>
    </div>"""

    rows = []
    for stock in data.portfolio_stocks:
        rows.append(_render_portfolio_row(stock))

    return f"""
    <div class="table-section">
        <h2>Portfolio</h2>
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th class="right">Price</th>
                    <th class="right">Daily Change</th>
                    <th class="right">Daily %</th>
                    <th class="right">Shares</th>
                    <th class="right">Market Value</th>
                    <th class="right">Cost Basis</th>
                    <th class="right">P&amp;L</th>
                    <th class="right">P&amp;L %</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>"""


def _render_portfolio_row(stock: "DashboardStock") -> str:
    """Render a single portfolio table row."""
    if stock.quote:
        price = _format_currency(stock.quote.current_price)
        daily_change = _format_currency(stock.quote.daily_change)
        daily_pct = _format_percent(stock.quote.daily_change_percent)
        daily_class = _change_class(stock.quote.daily_change_percent)
    else:
        price = "N/A"
        daily_change = "N/A"
        daily_pct = "N/A"
        daily_class = ""

    shares = f"{stock.shares_owned:,.0f}" if stock.shares_owned else "N/A"
    market_val = _format_currency(stock.market_value) if stock.market_value else "N/A"
    cost = _format_currency(stock.cost_basis_total) if stock.cost_basis_total else "N/A"

    if stock.unrealized_gain is not None:
        pl = _format_currency(stock.unrealized_gain)
        pl_class = _change_class(float(stock.unrealized_gain))
    else:
        pl = "N/A"
        pl_class = ""

    if stock.unrealized_gain_percent is not None:
        pl_pct = _format_percent(stock.unrealized_gain_percent)
        pl_pct_class = _change_class(stock.unrealized_gain_percent)
    else:
        pl_pct = "N/A"
        pl_pct_class = ""

    return f"""
                <tr>
                    <td class="ticker">{_esc(stock.ticker)}</td>
                    <td>{_esc(stock.company_name or '-')}</td>
                    <td class="right">{price}</td>
                    <td class="right {daily_class}">{daily_change}</td>
                    <td class="right {daily_class}">{daily_pct}</td>
                    <td class="right">{shares}</td>
                    <td class="right">{market_val}</td>
                    <td class="right">{cost}</td>
                    <td class="right {pl_class}">{pl}</td>
                    <td class="right {pl_pct_class}">{pl_pct}</td>
                </tr>"""


def _render_watchlist_table(data: "DashboardData") -> str:
    """Render the watchlist table."""
    if not data.watchlist_stocks:
        return ""

    rows = []
    for stock in data.watchlist_stocks:
        if stock.quote:
            price = _format_currency(stock.quote.current_price)
            daily_change = _format_currency(stock.quote.daily_change)
            daily_pct = _format_percent(stock.quote.daily_change_percent)
            daily_class = _change_class(stock.quote.daily_change_percent)
        else:
            price = "N/A"
            daily_change = "N/A"
            daily_pct = "N/A"
            daily_class = ""

        rows.append(f"""
                <tr>
                    <td class="ticker">{_esc(stock.ticker)}</td>
                    <td>{_esc(stock.company_name or '-')}</td>
                    <td class="right">{price}</td>
                    <td class="right {daily_class}">{daily_change}</td>
                    <td class="right {daily_class}">{daily_pct}</td>
                </tr>""")

    return f"""
    <div class="table-section">
        <h2>Watchlist</h2>
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Company</th>
                    <th class="right">Price</th>
                    <th class="right">Daily Change</th>
                    <th class="right">Daily %</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>"""


def _render_footer(data: "DashboardData") -> str:
    """Render the page footer."""
    timestamp = data.generated_at.strftime("%Y-%m-%d %H:%M:%S")
    return f"""
    <div class="footer">
        Generated by Insider Tracker at {_esc(timestamp)}
        &mdash; Big mover threshold: {data.big_mover_threshold:.0f}%
    </div>
    </div>"""
