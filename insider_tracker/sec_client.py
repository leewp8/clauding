"""SEC EDGAR API client for fetching Form 4 filings."""

import re
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from insider_tracker.models import (
    Company,
    InsiderInfo,
    InsiderRole,
    InsiderTransaction,
    OwnershipType,
    TransactionType,
)


class SECClient:
    """Client for interacting with SEC EDGAR API."""

    BASE_URL = "https://www.sec.gov"
    EDGAR_URL = "https://data.sec.gov"
    SUBMISSIONS_URL = f"{EDGAR_URL}/submissions"
    FILINGS_URL = f"{EDGAR_URL}/cgi-bin/browse-edgar"

    # SEC requires a User-Agent header with contact info
    DEFAULT_USER_AGENT = "InsiderTracker/1.0 (insider-tracker@example.com)"

    # Rate limiting - SEC allows 10 requests per second
    REQUEST_DELAY = 0.1

    def __init__(self, user_agent: Optional[str] = None):
        """Initialize SEC client.

        Args:
            user_agent: User agent string with contact info (required by SEC)
        """
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json, application/xml, text/html",
            }
        )
        self._last_request_time = 0.0
        self._ticker_to_cik_cache: dict[str, str] = {}

    def _rate_limit(self) -> None:
        """Enforce rate limiting for SEC requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _make_request(
        self, url: str, params: Optional[dict] = None, accept: Optional[str] = None
    ) -> requests.Response:
        """Make a rate-limited request to SEC."""
        self._rate_limit()
        headers = {}
        if accept:
            headers["Accept"] = accept
        response = self.session.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        return response

    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        """Convert a stock ticker to SEC CIK.

        Args:
            ticker: Stock ticker symbol (e.g., AAPL)

        Returns:
            CIK as a zero-padded 10-digit string, or None if not found
        """
        ticker = ticker.upper().strip()

        # Check cache first
        if ticker in self._ticker_to_cik_cache:
            return self._ticker_to_cik_cache[ticker]

        try:
            # Use SEC's company tickers JSON
            url = f"{self.EDGAR_URL}/files/company_tickers.json"
            response = self._make_request(url)
            data = response.json()

            for entry in data.values():
                if entry.get("ticker", "").upper() == ticker:
                    cik = str(entry.get("cik_str", "")).zfill(10)
                    self._ticker_to_cik_cache[ticker] = cik
                    return cik

            return None
        except Exception:
            return None

    def get_company_info(self, cik: str) -> Optional[Company]:
        """Get company information by CIK.

        Args:
            cik: Company CIK (will be zero-padded)

        Returns:
            Company object or None if not found
        """
        cik = cik.zfill(10)

        try:
            url = f"{self.SUBMISSIONS_URL}/CIK{cik}.json"
            response = self._make_request(url)
            data = response.json()

            tickers = data.get("tickers", [])
            ticker = tickers[0] if tickers else ""
            exchanges = data.get("exchanges", [])
            exchange = exchanges[0] if exchanges else None

            return Company(
                cik=cik,
                ticker=ticker,
                name=data.get("name", ""),
                exchange=exchange,
            )
        except Exception:
            return None

    def get_recent_form4_filings(
        self,
        cik: Optional[str] = None,
        ticker: Optional[str] = None,
        days: int = 30,
        limit: int = 100,
    ) -> list[InsiderTransaction]:
        """Get recent Form 4 filings for a company.

        Args:
            cik: Company CIK
            ticker: Company ticker (alternative to CIK)
            days: Number of days to look back
            limit: Maximum number of filings to return

        Returns:
            List of InsiderTransaction objects
        """
        if ticker and not cik:
            cik = self.ticker_to_cik(ticker)

        if not cik:
            return []

        cik = cik.zfill(10)
        transactions = []
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            # Get company submissions
            url = f"{self.SUBMISSIONS_URL}/CIK{cik}.json"
            response = self._make_request(url)
            data = response.json()

            company = Company(
                cik=cik,
                ticker=data.get("tickers", [""])[0],
                name=data.get("name", ""),
                exchange=data.get("exchanges", [None])[0],
            )

            # Get recent filings
            recent_filings = data.get("filings", {}).get("recent", {})
            forms = recent_filings.get("form", [])
            filing_dates = recent_filings.get("filingDate", [])
            accession_numbers = recent_filings.get("accessionNumber", [])
            primary_documents = recent_filings.get("primaryDocument", [])

            form4_count = 0
            for i, form in enumerate(forms):
                if form != "4":
                    continue

                if form4_count >= limit:
                    break

                filing_date_str = filing_dates[i]
                filing_date = datetime.strptime(filing_date_str, "%Y-%m-%d")

                if filing_date < cutoff_date:
                    continue

                accession = accession_numbers[i]
                primary_doc = primary_documents[i]

                # Fetch and parse the Form 4 XML
                filing_transactions = self._parse_form4_filing(
                    cik, accession, primary_doc, company, filing_date
                )
                transactions.extend(filing_transactions)
                form4_count += 1

        except Exception as e:
            print(f"Error fetching Form 4 filings: {e}")

        return transactions

    def _parse_form4_filing(
        self,
        company_cik: str,
        accession: str,
        primary_doc: str,
        company: Company,
        filing_date: datetime,
    ) -> list[InsiderTransaction]:
        """Parse a single Form 4 filing.

        Args:
            company_cik: Company CIK
            accession: Accession number
            primary_doc: Primary document filename
            company: Company object
            filing_date: Filing date

        Returns:
            List of InsiderTransaction objects from the filing
        """
        transactions = []
        accession_clean = accession.replace("-", "")

        try:
            # Try to get the XML version of the filing
            xml_doc = primary_doc.replace(".htm", ".xml").replace(".html", ".xml")
            url = f"{self.BASE_URL}/Archives/edgar/data/{company_cik.lstrip('0')}/{accession_clean}/{xml_doc}"

            try:
                response = self._make_request(url, accept="application/xml")
                return self._parse_form4_xml(
                    response.content, accession, company, filing_date, url
                )
            except requests.HTTPError:
                # Fall back to HTML parsing
                url = f"{self.BASE_URL}/Archives/edgar/data/{company_cik.lstrip('0')}/{accession_clean}/{primary_doc}"
                response = self._make_request(url)
                return self._parse_form4_html(
                    response.content, accession, company, filing_date, url
                )

        except Exception as e:
            print(f"Error parsing Form 4 filing {accession}: {e}")

        return transactions

    def _parse_form4_xml(
        self,
        content: bytes,
        accession: str,
        company: Company,
        filing_date: datetime,
        form_url: str,
    ) -> list[InsiderTransaction]:
        """Parse Form 4 XML content."""
        transactions = []

        try:
            root = ElementTree.fromstring(content)

            # Handle XML namespace
            ns = {"": ""}
            if root.tag.startswith("{"):
                ns_end = root.tag.find("}")
                ns[""] = root.tag[1:ns_end]

            def find_text(elem, path: str, default: str = "") -> str:
                if ns[""]:
                    path = "/".join(f"{{{ns['']}}}{p}" for p in path.split("/"))
                found = elem.find(path)
                return found.text.strip() if found is not None and found.text else default

            # Get reporting owner info
            owner_elem = root.find(".//reportingOwner") or root.find(
                f".//{{{ns['']}}}reportingOwner" if ns[""] else ".//reportingOwner"
            )
            if owner_elem is None:
                return transactions

            owner_id = owner_elem.find(".//reportingOwnerId") or owner_elem.find(
                f".//{{{ns['']}}}reportingOwnerId" if ns[""] else ".//reportingOwnerId"
            )
            owner_rel = owner_elem.find(".//reportingOwnerRelationship") or owner_elem.find(
                f".//{{{ns['']}}}reportingOwnerRelationship"
                if ns[""]
                else ".//reportingOwnerRelationship"
            )

            insider_cik = ""
            insider_name = ""
            if owner_id is not None:
                insider_cik = find_text(owner_id, "rptOwnerCik")
                insider_name = find_text(owner_id, "rptOwnerName")

            is_director = False
            is_officer = False
            is_ten_percent = False
            officer_title = None
            roles = []

            if owner_rel is not None:
                is_director = find_text(owner_rel, "isDirector") == "1"
                is_officer = find_text(owner_rel, "isOfficer") == "1"
                is_ten_percent = find_text(owner_rel, "isTenPercentOwner") == "1"
                officer_title = find_text(owner_rel, "officerTitle") or None

                if is_director:
                    roles.append(InsiderRole.DIRECTOR)
                if is_ten_percent:
                    roles.append(InsiderRole.TEN_PERCENT_OWNER)
                if officer_title:
                    role = self._parse_officer_role(officer_title)
                    if role:
                        roles.append(role)

            insider = InsiderInfo(
                cik=insider_cik,
                name=insider_name,
                roles=roles,
                is_director=is_director,
                is_officer=is_officer,
                is_ten_percent_owner=is_ten_percent,
                officer_title=officer_title,
            )

            # Parse non-derivative transactions
            for trans_elem in root.findall(".//nonDerivativeTransaction"):
                transaction = self._parse_transaction_element(
                    trans_elem, accession, company, insider, filing_date, form_url
                )
                if transaction:
                    transactions.append(transaction)

            # Parse derivative transactions
            for trans_elem in root.findall(".//derivativeTransaction"):
                transaction = self._parse_transaction_element(
                    trans_elem, accession, company, insider, filing_date, form_url, is_derivative=True
                )
                if transaction:
                    transactions.append(transaction)

        except Exception as e:
            print(f"Error parsing Form 4 XML: {e}")

        return transactions

    def _parse_transaction_element(
        self,
        elem: ElementTree.Element,
        accession: str,
        company: Company,
        insider: InsiderInfo,
        filing_date: datetime,
        form_url: str,
        is_derivative: bool = False,
    ) -> Optional[InsiderTransaction]:
        """Parse a transaction element from Form 4 XML."""

        def find_text(path: str, default: str = "") -> str:
            found = elem.find(f".//{path}")
            return found.text.strip() if found is not None and found.text else default

        def find_decimal(path: str) -> Optional[Decimal]:
            text = find_text(path)
            if text:
                try:
                    return Decimal(text.replace(",", ""))
                except InvalidOperation:
                    pass
            return None

        try:
            # Transaction date
            trans_date_str = find_text("transactionDate/value")
            trans_date = None
            if trans_date_str:
                try:
                    trans_date = datetime.strptime(trans_date_str, "%Y-%m-%d")
                except ValueError:
                    pass

            # Transaction coding
            trans_code = find_text("transactionCoding/transactionCode")
            if not trans_code:
                return None

            trans_type = self._map_transaction_code(trans_code)

            # Shares
            shares = find_decimal("transactionAmounts/transactionShares/value")
            if shares is None:
                shares = Decimal("0")

            # Price
            price = find_decimal("transactionAmounts/transactionPricePerShare/value")

            # Acquired/Disposed
            acq_disp = find_text("transactionAmounts/transactionAcquiredDisposedCode/value", "A")

            # Ownership type
            ownership = find_text("ownershipNature/directOrIndirectOwnership/value", "D")
            ownership_type = (
                OwnershipType.DIRECT if ownership == "D" else OwnershipType.INDIRECT
            )

            # Shares owned after
            shares_after = find_decimal("postTransactionAmounts/sharesOwnedFollowingTransaction/value")

            # Calculate total value
            total_value = None
            if price and shares:
                total_value = price * shares

            return InsiderTransaction(
                accession_number=accession,
                filing_date=filing_date,
                transaction_date=trans_date,
                company=company,
                insider=insider,
                transaction_type=trans_type,
                ownership_type=ownership_type,
                shares=shares,
                price_per_share=price,
                total_value=total_value,
                shares_owned_after=shares_after,
                acquired_disposed=acq_disp,
                form_url=form_url,
            )

        except Exception as e:
            print(f"Error parsing transaction element: {e}")
            return None

    def _parse_form4_html(
        self,
        content: bytes,
        accession: str,
        company: Company,
        filing_date: datetime,
        form_url: str,
    ) -> list[InsiderTransaction]:
        """Parse Form 4 HTML content (fallback)."""
        transactions = []

        try:
            soup = BeautifulSoup(content, "lxml")

            # Try to find the reporting owner
            owner_name = ""
            owner_tables = soup.find_all("table")
            for table in owner_tables:
                text = table.get_text()
                if "Reporting Owner" in text or "Name of Reporting Person" in text:
                    # Try to extract name from table
                    rows = table.find_all("tr")
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 2:
                            if "name" in cells[0].get_text().lower():
                                owner_name = cells[1].get_text().strip()
                                break
                    if owner_name:
                        break

            insider = InsiderInfo(
                cik="",
                name=owner_name or "Unknown",
                roles=[],
                is_director=False,
                is_officer=False,
                is_ten_percent_owner=False,
            )

            # Create a basic transaction record
            # HTML parsing is less reliable, so we create a minimal record
            transactions.append(
                InsiderTransaction(
                    accession_number=accession,
                    filing_date=filing_date,
                    transaction_date=None,
                    company=company,
                    insider=insider,
                    transaction_type=TransactionType.OTHER,
                    ownership_type=OwnershipType.DIRECT,
                    shares=Decimal("0"),
                    price_per_share=None,
                    total_value=None,
                    shares_owned_after=None,
                    acquired_disposed="A",
                    form_url=form_url,
                )
            )

        except Exception as e:
            print(f"Error parsing Form 4 HTML: {e}")

        return transactions

    def _map_transaction_code(self, code: str) -> TransactionType:
        """Map SEC transaction code to TransactionType."""
        code_map = {
            "P": TransactionType.PURCHASE,
            "S": TransactionType.SALE,
            "A": TransactionType.AWARD,
            "M": TransactionType.EXERCISE,
            "C": TransactionType.CONVERSION,
            "G": TransactionType.GIFT,
            "D": TransactionType.DISPOSITION,
            "F": TransactionType.SALE,  # Tax withholding
            "J": TransactionType.OTHER,  # Other acquisition
            "K": TransactionType.OTHER,  # Equity swap
            "U": TransactionType.OTHER,  # Tender of shares
            "W": TransactionType.OTHER,  # Acquisition by will
            "Z": TransactionType.OTHER,  # Voting trust
        }
        return code_map.get(code.upper(), TransactionType.OTHER)

    def _parse_officer_role(self, title: str) -> Optional[InsiderRole]:
        """Parse officer title to InsiderRole."""
        title_lower = title.lower()

        if "ceo" in title_lower or "chief executive" in title_lower:
            return InsiderRole.CEO
        elif "cfo" in title_lower or "chief financial" in title_lower:
            return InsiderRole.CFO
        elif "coo" in title_lower or "chief operating" in title_lower:
            return InsiderRole.COO
        elif "president" in title_lower:
            return InsiderRole.PRESIDENT
        elif "chairman" in title_lower or "chair" in title_lower:
            return InsiderRole.CHAIRMAN
        elif "general counsel" in title_lower or "chief legal" in title_lower:
            return InsiderRole.GENERAL_COUNSEL
        elif "controller" in title_lower:
            return InsiderRole.CONTROLLER
        elif "evp" in title_lower or "executive vice" in title_lower:
            return InsiderRole.EVP
        elif "svp" in title_lower or "senior vice" in title_lower:
            return InsiderRole.SVP
        elif "vp" in title_lower or "vice president" in title_lower:
            return InsiderRole.VP
        elif "officer" in title_lower:
            return InsiderRole.OFFICER
        elif "director" in title_lower:
            return InsiderRole.DIRECTOR

        return InsiderRole.OTHER

    def get_all_recent_form4s(
        self, days: int = 1, limit: int = 100
    ) -> list[InsiderTransaction]:
        """Get all recent Form 4 filings across all companies.

        Args:
            days: Number of days to look back
            limit: Maximum number of filings to return

        Returns:
            List of InsiderTransaction objects
        """
        transactions = []

        try:
            # Use SEC's full-text search for recent Form 4s
            url = f"{self.BASE_URL}/cgi-bin/browse-edgar"
            params = {
                "action": "getcurrent",
                "type": "4",
                "company": "",
                "dateb": "",
                "owner": "only",
                "count": str(limit),
                "output": "atom",
            }

            response = self._make_request(url, params=params)
            # Parse the Atom feed
            root = ElementTree.fromstring(response.content)

            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                try:
                    # Get the filing link
                    link_elem = entry.find("atom:link", ns)
                    if link_elem is None:
                        continue

                    link = link_elem.get("href", "")
                    if not link:
                        continue

                    # Extract accession number from link
                    match = re.search(r"/(\d{10})-(\d{2})-(\d+)", link)
                    if not match:
                        continue

                    # Get updated date
                    updated_elem = entry.find("atom:updated", ns)
                    if updated_elem is not None and updated_elem.text:
                        filing_date = datetime.fromisoformat(
                            updated_elem.text.replace("Z", "+00:00")
                        )
                        cutoff = datetime.now(filing_date.tzinfo) - timedelta(days=days)
                        if filing_date < cutoff:
                            continue

                except Exception:
                    continue

        except Exception as e:
            print(f"Error fetching recent Form 4s: {e}")

        return transactions

    def search_insider_filings(
        self,
        insider_name: Optional[str] = None,
        cik: Optional[str] = None,
        days: int = 90,
    ) -> list[InsiderTransaction]:
        """Search for Form 4 filings by a specific insider.

        Args:
            insider_name: Name of the insider to search for
            cik: CIK of the insider
            days: Number of days to look back

        Returns:
            List of InsiderTransaction objects
        """
        # This would require additional API calls to search by insider
        # For now, return empty list - could be enhanced with SEC full-text search
        return []
