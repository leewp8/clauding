"""Data models for insider trading tracking."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    """Type of insider transaction."""

    PURCHASE = "P"  # Open market or private purchase
    SALE = "S"  # Open market or private sale
    AWARD = "A"  # Grant, award, or other acquisition
    EXERCISE = "M"  # Exercise or conversion of derivative
    CONVERSION = "C"  # Conversion of derivative
    GIFT = "G"  # Gift
    DISPOSITION = "D"  # Disposition to issuer
    OTHER = "O"  # Other


class OwnershipType(str, Enum):
    """Type of ownership."""

    DIRECT = "D"  # Direct ownership
    INDIRECT = "I"  # Indirect ownership


class InsiderRole(str, Enum):
    """Role of the insider at the company."""

    CEO = "CEO"
    CFO = "CFO"
    COO = "COO"
    PRESIDENT = "President"
    CHAIRMAN = "Chairman"
    DIRECTOR = "Director"
    VP = "VP"
    SVP = "SVP"
    EVP = "EVP"
    OFFICER = "Officer"
    CONTROLLER = "Controller"
    GENERAL_COUNSEL = "General Counsel"
    TEN_PERCENT_OWNER = "10% Owner"
    OTHER = "Other"


class SignificanceLevel(str, Enum):
    """Level of significance for a transaction."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InsiderInfo(BaseModel):
    """Information about an insider."""

    cik: str = Field(..., description="Central Index Key for the insider")
    name: str = Field(..., description="Name of the insider")
    roles: list[InsiderRole] = Field(default_factory=list, description="Roles at the company")
    is_director: bool = Field(default=False, description="Whether the insider is a director")
    is_officer: bool = Field(default=False, description="Whether the insider is an officer")
    is_ten_percent_owner: bool = Field(
        default=False, description="Whether the insider is a 10% owner"
    )
    officer_title: Optional[str] = Field(default=None, description="Officer title if applicable")


class Company(BaseModel):
    """Company information."""

    cik: str = Field(..., description="Central Index Key for the company")
    ticker: str = Field(..., description="Stock ticker symbol")
    name: str = Field(..., description="Company name")
    exchange: Optional[str] = Field(default=None, description="Stock exchange")


class InsiderTransaction(BaseModel):
    """A single insider transaction from Form 4."""

    accession_number: str = Field(..., description="SEC accession number for the filing")
    filing_date: datetime = Field(..., description="Date the Form 4 was filed")
    transaction_date: Optional[datetime] = Field(
        default=None, description="Date of the transaction"
    )
    company: Company = Field(..., description="Company information")
    insider: InsiderInfo = Field(..., description="Insider information")
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    ownership_type: OwnershipType = Field(
        default=OwnershipType.DIRECT, description="Type of ownership"
    )
    shares: Decimal = Field(..., description="Number of shares transacted")
    price_per_share: Optional[Decimal] = Field(
        default=None, description="Price per share if available"
    )
    total_value: Optional[Decimal] = Field(
        default=None, description="Total transaction value"
    )
    shares_owned_after: Optional[Decimal] = Field(
        default=None, description="Shares owned after transaction"
    )
    acquired_disposed: str = Field(
        default="A", description="A=Acquired, D=Disposed"
    )
    footnotes: list[str] = Field(default_factory=list, description="Transaction footnotes")
    form_url: Optional[str] = Field(default=None, description="URL to the Form 4 filing")

    @property
    def is_purchase(self) -> bool:
        """Check if this is a purchase transaction."""
        return (
            self.transaction_type == TransactionType.PURCHASE
            and self.acquired_disposed == "A"
        )

    @property
    def is_sale(self) -> bool:
        """Check if this is a sale transaction."""
        return (
            self.transaction_type == TransactionType.SALE
            and self.acquired_disposed == "D"
        )

    @property
    def is_open_market(self) -> bool:
        """Check if this is an open market transaction (most significant)."""
        return self.transaction_type in [TransactionType.PURCHASE, TransactionType.SALE]


class WatchlistEntry(BaseModel):
    """An entry in the watchlist."""

    ticker: str = Field(..., description="Stock ticker symbol")
    cik: Optional[str] = Field(default=None, description="Company CIK if known")
    company_name: Optional[str] = Field(default=None, description="Company name if known")
    added_date: datetime = Field(
        default_factory=datetime.now, description="When the entry was added"
    )
    notes: Optional[str] = Field(default=None, description="User notes")
    is_portfolio: bool = Field(
        default=False, description="Whether this is in the portfolio (vs just watchlist)"
    )
    shares_owned: Optional[Decimal] = Field(
        default=None, description="Number of shares owned if in portfolio"
    )
    average_cost: Optional[Decimal] = Field(
        default=None, description="Average cost basis if in portfolio"
    )


class AlertThresholds(BaseModel):
    """Configurable thresholds for alerts."""

    min_transaction_value: Decimal = Field(
        default=Decimal("10000"), description="Minimum transaction value to alert"
    )
    min_shares: int = Field(default=1000, description="Minimum shares to alert")
    large_transaction_value: Decimal = Field(
        default=Decimal("100000"), description="Value threshold for large transaction"
    )
    significant_transaction_value: Decimal = Field(
        default=Decimal("500000"), description="Value threshold for significant transaction"
    )
    critical_transaction_value: Decimal = Field(
        default=Decimal("1000000"), description="Value threshold for critical transaction"
    )
    ownership_change_percent: Decimal = Field(
        default=Decimal("10"), description="Percent ownership change to flag"
    )
    cluster_window_days: int = Field(
        default=7, description="Days to look for clustered transactions"
    )
    cluster_min_insiders: int = Field(
        default=3, description="Minimum insiders for cluster alert"
    )
