from __future__ import annotations

import pandas as pd
import yfinance as yf

NA_VALUE = "N/A"


def safe_series(df: pd.DataFrame | None) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype="float64")
    return df.iloc[:, 0]


def _normalize_index(obj: pd.Series | pd.DataFrame | None) -> dict[str, str]:
    if obj is None or obj.empty:
        return {}
    return {str(idx).strip().lower(): idx for idx in obj.index}


def _is_valid_number(value) -> bool:
    if value in [None, NA_VALUE]:
        return False
    try:
        return pd.notna(value)
    except Exception:
        return False


def _to_python_value(value):
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def get_latest_value(series: pd.Series | None, labels: list[str]):
    if series is None or series.empty:
        return NA_VALUE

    normalized = _normalize_index(series)
    for label in labels:
        key = normalized.get(label.strip().lower())
        if key is not None:
            value = series.get(key, pd.NA)
            return _to_python_value(value) if pd.notna(value) else NA_VALUE

    return NA_VALUE


def get_ttm_value(df: pd.DataFrame | None, labels: list[str]):
    if df is None or df.empty:
        return NA_VALUE

    normalized = _normalize_index(df)
    for label in labels:
        key = normalized.get(label.strip().lower())
        if key is not None:
            values = pd.to_numeric(df.loc[key].iloc[:4], errors="coerce")
            if not values.isna().all():
                return _to_python_value(values.sum())

    return NA_VALUE


def get_info_value(info: dict, keys: list[str]):
    for key in keys:
        value = info.get(key)
        if value is not None:
            return value
    return NA_VALUE


def get_fast_info_value(stock, keys: list[str]):
    try:
        fast_info = stock.fast_info
    except Exception:
        return NA_VALUE

    for key in keys:
        try:
            value = fast_info.get(key) if hasattr(fast_info, "get") else fast_info[key]
        except Exception:
            continue
        if value is not None and pd.notna(value):
            return _to_python_value(value)
    return NA_VALUE


def get_history_metadata_value(stock, keys: list[str]):
    try:
        metadata = stock.get_history_metadata() or {}
    except Exception:
        return NA_VALUE

    for key in keys:
        value = metadata.get(key)
        if value is not None and pd.notna(value):
            return _to_python_value(value)
    return NA_VALUE


def get_company_name(stock, ticker: str, info: dict):
    name = get_info_value(info, ["longName", "shortName"])
    if name != NA_VALUE:
        return name

    name = get_history_metadata_value(stock, ["longName", "shortName"])
    if name != NA_VALUE:
        return name

    try:
        quotes = yf.Search(ticker, max_results=8).quotes or []
    except Exception:
        return NA_VALUE

    normalized_ticker = ticker.strip().upper()
    for quote in quotes:
        if str(quote.get("symbol", "")).strip().upper() != normalized_ticker:
            continue
        for key in ["longname", "shortname", "longName", "shortName"]:
            value = quote.get(key)
            if value:
                return value
    return NA_VALUE


def get_dividends_per_share(stock, quarterly_cashflow, total_shares_outstanding):
    try:
        history = stock.history(period="1y", auto_adjust=False, actions=True)
        if history is not None and not history.empty and "Dividends" in history.columns:
            dividends = pd.to_numeric(history["Dividends"], errors="coerce").dropna()
            if not dividends.empty:
                return _to_python_value(dividends.sum())
    except Exception:
        pass

    total_dividends_paid = get_ttm_value(
        quarterly_cashflow,
        ["CommonStockDividendPaid", "CashDividendsPaid", "DividendsPaid"],
    )
    if (
        total_dividends_paid != NA_VALUE
        and total_shares_outstanding != NA_VALUE
        and total_shares_outstanding not in [0, None]
    ):
        return abs(total_dividends_paid) / total_shares_outstanding
    return NA_VALUE


def sum_available_values(*values):
    numeric_values = [value for value in values if _is_valid_number(value)]
    if not numeric_values:
        return NA_VALUE
    return sum(numeric_values)


def get_ttm_ebitda(quarterly_financials: pd.DataFrame | None, quarterly_cashflow: pd.DataFrame | None):
    direct_ebitda = get_ttm_value(
        quarterly_financials,
        [
            "EBITDA",
            "NormalizedEBITDA",
        ],
    )
    if direct_ebitda != NA_VALUE:
        return direct_ebitda

    ebit = get_ttm_value(
        quarterly_financials,
        [
            "EBIT",
            "OperatingIncome",
            "PretaxIncome",
        ],
    )
    depreciation_and_amortization = get_ttm_value(
        quarterly_cashflow,
        [
            "DepreciationAndAmortization",
            "DepreciationAmortizationDepletion",
            "Depreciation",
            "Amortization",
        ],
    )
    return sum_available_values(ebit, depreciation_and_amortization)


def get_current_assets(latest_balance_sheet: pd.Series | None):
    direct_current_assets = get_latest_value(
        latest_balance_sheet,
        [
            "CurrentAssets",
            "TotalCurrentAssets",
        ],
    )
    if direct_current_assets != NA_VALUE:
        return direct_current_assets

    cash = get_latest_value(
        latest_balance_sheet,
        [
            "CashAndCashEquivalents",
            "CashCashEquivalentsAndShortTermInvestments",
            "CashAndShortTermInvestments",
        ],
    )
    receivables = get_latest_value(
        latest_balance_sheet,
        [
            "AccountsReceivable",
            "Receivables",
            "NetReceivables",
            "PremiumsReceivable",
        ],
    )
    inventory = get_latest_value(latest_balance_sheet, ["Inventory"])
    other_current_assets = get_latest_value(
        latest_balance_sheet,
        [
            "OtherCurrentAssets",
            "PrepaidAssets",
        ],
    )
    return sum_available_values(cash, receivables, inventory, other_current_assets)


def get_current_liabilities(latest_balance_sheet: pd.Series | None):
    direct_current_liabilities = get_latest_value(
        latest_balance_sheet,
        [
            "CurrentLiabilities",
            "TotalCurrentLiabilities",
        ],
    )
    if direct_current_liabilities != NA_VALUE:
        return direct_current_liabilities

    payables = get_latest_value(
        latest_balance_sheet,
        [
            "AccountsPayable",
            "Payables",
            "PayablesAndAccruedExpenses",
            "AccountsPayableAndAccruedExpense",
        ],
    )
    current_debt = get_latest_value(
        latest_balance_sheet,
        [
            "CurrentDebt",
            "CurrentDebtAndCapitalLeaseObligation",
            "CurrentCapitalLeaseObligation",
        ],
    )
    other_current_liabilities = get_latest_value(
        latest_balance_sheet,
        [
            "OtherCurrentLiabilities",
            "CurrentDeferredLiabilities",
            "CurrentDeferredRevenue",
        ],
    )
    return sum_available_values(payables, current_debt, other_current_liabilities)


def _clean_excel_value(value):
    if value is None:
        return NA_VALUE
    if isinstance(value, float) and pd.isna(value):
        return NA_VALUE
    if value is pd.NA:
        return NA_VALUE
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def fetch_financial_data(ticker: str) -> tuple[dict | None, list[str]]:
    """Fetch financial statement and profile data for one ticker.

    Returns a tuple of (data, log_messages). Missing values are returned as N/A.
    """
    messages: list[str] = []
    try:
        normalized_ticker = str(ticker).strip().upper()
        messages.append(f"Fetching data for {normalized_ticker}")
        stock = yf.Ticker(normalized_ticker)

        quarterly_financials = stock.get_income_stmt(freq="quarterly", pretty=False)
        quarterly_balance_sheet = stock.get_balance_sheet(freq="quarterly", pretty=False)
        quarterly_cashflow = stock.get_cashflow(freq="quarterly", pretty=False)
        latest_balance_sheet = safe_series(quarterly_balance_sheet)

        try:
            info = stock.info or {}
        except Exception as exc:
            messages.append(f"Could not fetch profile info for {normalized_ticker}: {exc}")
            info = {}

        total_shares_outstanding = get_fast_info_value(stock, ["shares"])
        if total_shares_outstanding == NA_VALUE:
            total_shares_outstanding = get_info_value(info, ["sharesOutstanding"])
        if total_shares_outstanding == NA_VALUE:
            total_shares_outstanding = get_latest_value(
                latest_balance_sheet,
                ["OrdinarySharesNumber", "ShareIssued"],
            )

        price_per_share = get_fast_info_value(stock, ["last_price"])
        if price_per_share == NA_VALUE:
            price_per_share = get_info_value(info, ["currentPrice", "regularMarketPrice"])
        if price_per_share == NA_VALUE:
            price_per_share = get_history_metadata_value(stock, ["regularMarketPrice"])

        dividends_per_share = get_dividends_per_share(
            stock,
            quarterly_cashflow,
            total_shares_outstanding,
        )

        depreciation = get_ttm_value(
            quarterly_cashflow,
            [
                "DepreciationAndAmortization",
                "DepreciationAmortizationDepletion",
                "Depreciation",
                "Amortization",
            ],
        )

        data = {
            "Name": get_company_name(stock, normalized_ticker, info),
            "Price per Share": price_per_share,
            "Total Shares Outstanding": total_shares_outstanding,
            "Total Debt": get_latest_value(latest_balance_sheet, ["TotalDebt"]),
            "Interest Expense": get_ttm_value(quarterly_financials, ["InterestExpense", "NetInterestIncome"]),
            "Cash": get_latest_value(
                latest_balance_sheet,
                [
                    "CashAndCashEquivalents",
                    "CashCashEquivalentsAndShortTermInvestments",
                    "CashAndShortTermInvestments",
                ],
            ),
            "Capital Expenditure": get_ttm_value(quarterly_cashflow, ["CapitalExpenditure"]),
            "LTM Revenue": get_ttm_value(quarterly_financials, ["TotalRevenue"]),
            "Gross Profit": get_ttm_value(quarterly_financials, ["GrossProfit"]),
            "Net Income": get_ttm_value(quarterly_financials, ["NetIncome"]),
            "LTM EBIT": get_ttm_value(quarterly_financials, ["EBIT", "OperatingIncome", "PretaxIncome"]),
            "LTM EBITDA": get_ttm_ebitda(quarterly_financials, quarterly_cashflow),
            "Diluted EPS": get_ttm_value(quarterly_financials, ["DilutedEPS"]),
            "Forward EPS": get_info_value(info, ["epsForward"]),
            "Current EPS": get_info_value(info, ["trailingEps"]),
            "Dividends Per Share": dividends_per_share,
            "Beta": get_info_value(info, ["beta"]),
            "Accounts Receivable": get_latest_value(latest_balance_sheet, ["AccountsReceivable", "Receivables", "NetReceivables", "PremiumsReceivable"]),
            "Inventory": get_latest_value(latest_balance_sheet, ["Inventory"]),
            "Current Assets": get_current_assets(latest_balance_sheet),
            "Accounts Payable": get_latest_value(latest_balance_sheet, ["AccountsPayable", "Payables", "PayablesAndAccruedExpenses"]),
            "Current Liabilities": get_current_liabilities(latest_balance_sheet),
            "Total Assets": get_latest_value(latest_balance_sheet, ["TotalAssets"]),
            "Total Liabilities": get_latest_value(
                latest_balance_sheet,
                ["TotalLiabilitiesNetMinorityInterest", "TotalLiabilities"],
            ),
            "Description": get_info_value(info, ["longBusinessSummary"]),
            "Depreciation": depreciation,
            "OCF": get_ttm_value(
                quarterly_cashflow,
                ["OperatingCashFlow", "CashFlowFromContinuingOperatingActivities"],
            ),
        }

        return {key: _clean_excel_value(value) for key, value in data.items()}, messages

    except Exception as exc:
        messages.append(f"Error fetching data for {ticker}: {exc}")
        return None, messages
