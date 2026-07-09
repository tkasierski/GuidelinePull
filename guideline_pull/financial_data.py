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

        total_dividends_paid = get_ttm_value(
            quarterly_cashflow,
            ["CommonStockDividendPaid", "CashDividendsPaid", "DividendsPaid"],
        )
        total_shares_outstanding = get_info_value(info, ["sharesOutstanding"])

        if (
            total_dividends_paid != NA_VALUE
            and total_shares_outstanding != NA_VALUE
            and total_shares_outstanding not in [0, None]
        ):
            dividends_per_share = total_dividends_paid / total_shares_outstanding
        else:
            dividends_per_share = NA_VALUE

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
            "Name": get_info_value(info, ["longName", "shortName"]),
            "Price per Share": get_info_value(info, ["currentPrice", "regularMarketPrice"]),
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
