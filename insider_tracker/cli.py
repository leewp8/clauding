"""Command-line interface for insider trading tracker."""

from decimal import Decimal
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from insider_tracker.models import SignificanceLevel
from insider_tracker.tracker import InsiderTracker

console = Console()


def get_tracker(data_dir: Optional[str] = None) -> InsiderTracker:
    """Get or create tracker instance."""
    path = Path(data_dir) if data_dir else None
    return InsiderTracker(data_dir=path)


def format_currency(value: Optional[Decimal]) -> str:
    """Format a decimal value as currency."""
    if value is None:
        return "N/A"
    return f"${value:,.0f}"


def significance_style(level: SignificanceLevel) -> str:
    """Get rich style for significance level."""
    styles = {
        SignificanceLevel.LOW: "dim",
        SignificanceLevel.MEDIUM: "yellow",
        SignificanceLevel.HIGH: "orange1",
        SignificanceLevel.CRITICAL: "bold red",
    }
    return styles.get(level, "")


def significance_emoji(level: SignificanceLevel) -> str:
    """Get emoji for significance level."""
    emojis = {
        SignificanceLevel.LOW: "",
        SignificanceLevel.MEDIUM: "[yellow]*[/yellow]",
        SignificanceLevel.HIGH: "[orange1]**[/orange1]",
        SignificanceLevel.CRITICAL: "[red]***[/red]",
    }
    return emojis.get(level, "")


@click.group()
@click.option(
    "--data-dir",
    "-d",
    type=click.Path(),
    help="Data directory for storing watchlist and alerts",
)
@click.pass_context
def main(ctx, data_dir):
    """Insider Trading Tracker - Monitor SEC Form 4 filings.

    Track insider buying and selling for companies in your watchlist
    and portfolio, with alerts for significant transactions.
    """
    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data_dir


@main.command()
@click.pass_context
def status(ctx):
    """Show tracker status and summary."""
    tracker = get_tracker(ctx.obj.get("data_dir"))
    status_info = tracker.get_status()

    panel = Panel(
        f"""[bold]Insider Trading Tracker[/bold]

Watchlist: {status_info['watchlist_count']} companies
Portfolio: {status_info['portfolio_count']} holdings
Total tracked: {status_info['total_tracked']}

Unread alerts: {status_info['unread_alerts']}

Data directory: {status_info['data_dir']}""",
        title="Status",
        border_style="blue",
    )
    console.print(panel)


# Watchlist commands
@main.group()
def watchlist():
    """Manage your watchlist of companies."""
    pass


@watchlist.command("add")
@click.argument("ticker")
@click.option("--notes", "-n", help="Notes about this ticker")
@click.pass_context
def watchlist_add(ctx, ticker, notes):
    """Add a ticker to your watchlist."""
    tracker = get_tracker(ctx.obj.get("data_dir"))

    with console.status(f"Adding {ticker.upper()}..."):
        result = tracker.add_to_watchlist(ticker, notes=notes)

    entry = result["entry"]
    console.print(f"[green]Added[/green] [bold]{entry.ticker}[/bold]", end="")
    if entry.company_name:
        console.print(f" ({entry.company_name})")
    else:
        console.print()

    if result["recent_transactions"] > 0:
        console.print(
            f"  [dim]{result['recent_transactions']} insider transactions in last 30 days[/dim]"
        )


@watchlist.command("remove")
@click.argument("ticker")
@click.pass_context
def watchlist_remove(ctx, ticker):
    """Remove a ticker from your watchlist."""
    tracker = get_tracker(ctx.obj.get("data_dir"))

    if tracker.remove_from_watchlist(ticker):
        console.print(f"[green]Removed[/green] {ticker.upper()}")
    else:
        console.print(f"[red]Not found:[/red] {ticker.upper()}")


@watchlist.command("list")
@click.pass_context
def watchlist_list(ctx):
    """List all companies in your watchlist."""
    tracker = get_tracker(ctx.obj.get("data_dir"))

    entries = tracker.watchlist.get_watchlist()
    if not entries:
        console.print("[dim]No companies in watchlist. Add some with: watchlist add TICKER[/dim]")
        return

    table = Table(title="Watchlist")
    table.add_column("Ticker", style="bold")
    table.add_column("Company")
    table.add_column("Added")
    table.add_column("Notes")

    for entry in entries:
        table.add_row(
            entry.ticker,
            entry.company_name or "-",
            entry.added_date.strftime("%Y-%m-%d"),
            entry.notes or "-",
        )

    console.print(table)


@watchlist.command("import")
@click.argument("tickers", nargs=-1)
@click.pass_context
def watchlist_import(ctx, tickers):
    """Bulk import multiple tickers to watchlist.

    Example: watchlist import AAPL MSFT GOOGL
    """
    tracker = get_tracker(ctx.obj.get("data_dir"))

    with console.status("Importing tickers..."):
        entries = tracker.watchlist.import_tickers(list(tickers))

    console.print(f"[green]Imported {len(entries)} tickers[/green]")
    for entry in entries:
        console.print(f"  {entry.ticker}: {entry.company_name or 'Unknown'}")


# Portfolio commands
@main.group()
def portfolio():
    """Manage your portfolio holdings."""
    pass


@portfolio.command("add")
@click.argument("ticker")
@click.option("--shares", "-s", type=float, required=True, help="Number of shares owned")
@click.option("--cost", "-c", type=float, help="Average cost basis per share")
@click.option("--notes", "-n", help="Notes about this holding")
@click.pass_context
def portfolio_add(ctx, ticker, shares, cost, notes):
    """Add a holding to your portfolio."""
    tracker = get_tracker(ctx.obj.get("data_dir"))

    shares_dec = Decimal(str(shares))
    cost_dec = Decimal(str(cost)) if cost else None

    with console.status(f"Adding {ticker.upper()}..."):
        result = tracker.add_to_watchlist(
            ticker,
            is_portfolio=True,
            shares=shares_dec,
            cost_basis=cost_dec,
            notes=notes,
        )

    entry = result["entry"]
    console.print(f"[green]Added to portfolio:[/green] [bold]{entry.ticker}[/bold]")
    console.print(f"  Shares: {shares_dec:,.0f}")
    if cost_dec:
        console.print(f"  Cost basis: ${cost_dec:,.2f}")


@portfolio.command("list")
@click.pass_context
def portfolio_list(ctx):
    """List all holdings in your portfolio."""
    tracker = get_tracker(ctx.obj.get("data_dir"))

    entries = tracker.watchlist.get_portfolio()
    if not entries:
        console.print("[dim]No holdings in portfolio. Add some with: portfolio add TICKER -s SHARES[/dim]")
        return

    table = Table(title="Portfolio Holdings")
    table.add_column("Ticker", style="bold")
    table.add_column("Company")
    table.add_column("Shares", justify="right")
    table.add_column("Cost Basis", justify="right")
    table.add_column("Notes")

    for entry in entries:
        table.add_row(
            entry.ticker,
            entry.company_name or "-",
            f"{entry.shares_owned:,.0f}" if entry.shares_owned else "-",
            f"${entry.average_cost:,.2f}" if entry.average_cost else "-",
            entry.notes or "-",
        )

    console.print(table)


@portfolio.command("exposure")
@click.pass_context
def portfolio_exposure(ctx):
    """Analyze insider trading exposure for your portfolio."""
    tracker = get_tracker(ctx.obj.get("data_dir"))

    with console.status("Analyzing portfolio exposure..."):
        exposure = tracker.get_portfolio_exposure()

    if not exposure["holdings"]:
        console.print("[dim]No portfolio holdings to analyze[/dim]")
        return

    # Summary panel
    sentiment_color = {
        "bullish": "green",
        "bearish": "red",
        "neutral": "yellow",
    }.get(exposure["net_insider_sentiment"], "white")

    panel = Panel(
        f"""[bold]30-Day Insider Activity Summary[/bold]

Total insider buying: [green]{format_currency(exposure['total_insider_buys_30d'])}[/green]
Total insider selling: [red]{format_currency(exposure['total_insider_sells_30d'])}[/red]

Net sentiment: [{sentiment_color}]{exposure['net_insider_sentiment'].upper()}[/{sentiment_color}]""",
        title="Portfolio Exposure",
        border_style="blue",
    )
    console.print(panel)

    # Holdings table
    table = Table(title="Holdings Detail")
    table.add_column("Ticker", style="bold")
    table.add_column("Insider Buys", justify="right", style="green")
    table.add_column("Insider Sells", justify="right", style="red")
    table.add_column("Net", justify="right")
    table.add_column("Transactions", justify="right")

    for holding in exposure["holdings"]:
        net = holding["net_activity"]
        net_style = "green" if net > 0 else "red" if net < 0 else ""
        table.add_row(
            holding["ticker"],
            format_currency(holding["insider_buys_30d"]),
            format_currency(holding["insider_sells_30d"]),
            Text(format_currency(net), style=net_style),
            str(holding["transaction_count"]),
        )

    console.print(table)


# Scan commands
@main.command()
@click.option("--days", "-d", default=7, help="Days to look back (default: 7)")
@click.option(
    "--significance",
    "-s",
    type=click.Choice(["low", "medium", "high", "critical"]),
    default="medium",
    help="Minimum significance level",
)
@click.pass_context
def scan(ctx, days, significance):
    """Scan watchlist for insider activity and create alerts."""
    tracker = get_tracker(ctx.obj.get("data_dir"))

    sig_level = SignificanceLevel(significance)

    with console.status(f"Scanning {tracker.watchlist.count()} tickers..."):
        alerts = tracker.scan_watchlist(days=days, min_significance=sig_level)

    if alerts:
        console.print(f"\n[bold green]Found {len(alerts)} significant transactions:[/bold green]\n")
        for alert in alerts:
            style = significance_style(alert.significance)
            console.print(f"[{style}]{significance_emoji(alert.significance)} {alert.title}[/{style}]")
            console.print(f"  {alert.description}")
            for detail in alert.details[:3]:
                console.print(f"  [dim]- {detail}[/dim]")
            console.print()
    else:
        console.print("[dim]No significant insider activity found[/dim]")


@main.command()
@click.argument("ticker")
@click.option("--days", "-d", default=90, help="Days to look back (default: 90)")
@click.pass_context
def lookup(ctx, ticker, days):
    """Look up insider activity for a specific ticker."""
    tracker = get_tracker(ctx.obj.get("data_dir"))

    with console.status(f"Fetching insider activity for {ticker.upper()}..."):
        summary = tracker.get_ticker_summary(ticker, days=days)

    stats = summary["stats"]

    # Summary panel
    panel = Panel(
        f"""[bold]{summary['ticker']}[/bold] - {days} Day Summary

Transactions: {stats['total_transactions']}
  Purchases: [green]{stats['purchases']}[/green] ({format_currency(stats['total_purchase_value'])})
  Sales: [red]{stats['sales']}[/red] ({format_currency(stats['total_sale_value'])})

Unique insiders: {stats['unique_insiders']}
Significant transactions: {summary['significant_count']}
Net direction: {stats['net_direction'].upper()}""",
        title="Insider Activity",
        border_style="blue",
    )
    console.print(panel)

    # Insiders table
    if summary["insiders"]:
        table = Table(title="Insiders")
        table.add_column("Name")
        table.add_column("Title")
        table.add_column("Buys", justify="right", style="green")
        table.add_column("Sells", justify="right", style="red")
        table.add_column("Total Bought", justify="right")
        table.add_column("Total Sold", justify="right")

        for insider in summary["insiders"]:
            table.add_row(
                insider["name"],
                insider["title"] or "-",
                str(insider["purchases"]),
                str(insider["sales"]),
                format_currency(insider["total_bought"]),
                format_currency(insider["total_sold"]),
            )

        console.print(table)

    # Recent significant transactions
    significant = [a for a in summary["analyses"] if a.is_significant]
    if significant:
        console.print("\n[bold]Significant Transactions:[/bold]")
        for analysis in significant[:10]:
            t = analysis.transaction
            style = significance_style(analysis.significance)
            action = "bought" if t.is_purchase else "sold" if t.is_sale else "transacted"
            date_str = t.transaction_date.strftime("%Y-%m-%d") if t.transaction_date else "N/A"

            console.print(
                f"\n[{style}]{significance_emoji(analysis.significance)} "
                f"{t.insider.name} {action} {t.shares:,.0f} shares[/{style}]"
            )
            console.print(f"  Date: {date_str}")
            if t.total_value:
                console.print(f"  Value: {format_currency(t.total_value)}")
            for reason in analysis.reasons[:3]:
                console.print(f"  [dim]- {reason}[/dim]")


# Alert commands
@main.group()
def alerts():
    """Manage alerts for insider activity."""
    pass


@alerts.command("list")
@click.option("--ticker", "-t", help="Filter by ticker")
@click.option("--unread", "-u", is_flag=True, help="Show only unread alerts")
@click.option("--limit", "-l", default=20, help="Maximum alerts to show")
@click.pass_context
def alerts_list(ctx, ticker, unread, limit):
    """List recent alerts."""
    tracker = get_tracker(ctx.obj.get("data_dir"))

    alert_list = tracker.get_alerts(
        ticker=ticker,
        unread_only=unread,
        limit=limit,
    )

    if not alert_list:
        console.print("[dim]No alerts found[/dim]")
        return

    for alert in alert_list:
        style = significance_style(alert.significance)
        read_indicator = "" if alert.is_read else "[bold cyan]NEW[/bold cyan] "

        console.print(
            f"\n{read_indicator}[{style}]{significance_emoji(alert.significance)} "
            f"{alert.title}[/{style}]"
        )
        console.print(f"  {alert.description}")
        console.print(f"  [dim]{alert.created_at.strftime('%Y-%m-%d %H:%M')} | ID: {alert.id}[/dim]")


@alerts.command("read")
@click.argument("alert_id", required=False)
@click.option("--all", "-a", "mark_all", is_flag=True, help="Mark all alerts as read")
@click.pass_context
def alerts_read(ctx, alert_id, mark_all):
    """Mark alert(s) as read."""
    tracker = get_tracker(ctx.obj.get("data_dir"))

    if mark_all:
        count = tracker.alert_manager.mark_all_read()
        console.print(f"[green]Marked {count} alerts as read[/green]")
    elif alert_id:
        if tracker.alert_manager.mark_read(alert_id):
            console.print(f"[green]Marked alert {alert_id} as read[/green]")
        else:
            console.print(f"[red]Alert not found: {alert_id}[/red]")
    else:
        console.print("[red]Specify an alert ID or use --all[/red]")


@alerts.command("dismiss")
@click.argument("alert_id")
@click.pass_context
def alerts_dismiss(ctx, alert_id):
    """Dismiss an alert."""
    tracker = get_tracker(ctx.obj.get("data_dir"))

    if tracker.alert_manager.dismiss(alert_id):
        console.print(f"[green]Dismissed alert {alert_id}[/green]")
    else:
        console.print(f"[red]Alert not found: {alert_id}[/red]")


@alerts.command("clear")
@click.option("--days", "-d", default=30, help="Clear alerts older than N days")
@click.pass_context
def alerts_clear(ctx, days):
    """Clear old alerts."""
    tracker = get_tracker(ctx.obj.get("data_dir"))
    count = tracker.alert_manager.clear_old_alerts(days=days)
    console.print(f"[green]Cleared {count} old alerts[/green]")


if __name__ == "__main__":
    main()
