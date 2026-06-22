from __future__ import annotations

import pandas as pd
import yfinance as yf


def safe_series(df: pd.DataFrame | None) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype="float64")
    return df.iloc[:, 0]


def get_latest_value(series: pd.Series | None, labels: list[str]):
    if series is None or series.empty:
        return "N/A"

    normalized = {str(idx).strip().lower(): idx for idx in series.index}
    for label in labels:
        key = normalized.get(label.strip().lower())
        if key is not None:
            value = series.get(key, pd.NA)
            return value.item() if hasattr(value, "item") and pd.notna(value) else (value if pd.notna(value) else "N/A")

    return "N/A"


def get_ttm_value(df: pd.DataFrame | None, labels: list[str]):
    if df is None or df.empty:
        return "N/A"

    normalized = {str(idx).strip().lower(): idx for idx in df.index}
    for label in labels:
        key = normalized.get(label.strip().lower())
        if key is not None:
            values = pd.to_numeric(df.loc[key].iloc[:4], errors="coerce")
            if not values.isna().all():
                value = values.sum()
                return value.item() if hasattr(value, "item") else value

    return "N/A"


def get_info_value(info: dict, keys: list[str]):
    for key in keys:
        value = info.get(key)
        if value is not None:
            return value
    return "N/A"


def _clean_excel_value(value):
    if value is None:
        return "N/A"
    if isinstance(value, float) and pd.isna(value):
        return "N/A"
    if value is pd.NA:
        return "N/A"
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
            total_dividends_paid != "N/A"
            and total_shares_outstanding != "N/A"
            and total_shares_outstanding not in [0, None]
        ):
            dividends_per_share = total_dividends_paid / total_shares_outstanding
        else:
            dividends_per_share = "N/A"

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
            "LTM EBIT": get_ttm_value(quarterly_financials, ["EBIT", "OperatingIncome"]),
            "LTM EBITDA": get_ttm_value(quarterly_financials, ["EBITDA"]),
            "Diluted EPS": get_ttm_value(quarterly_financials, ["DilutedEPS"]),
            "Forward EPS": get_info_value(info, ["epsForward"]),
            "Current EPS": get_info_value(info, ["trailingEps"]),
            "Dividends Per Share": dividends_per_share,
            "Beta": get_info_value(info, ["beta"]),
            "Accounts Receivable": get_latest_value(latest_balance_sheet, ["AccountsReceivable", "Receivables"]),
            "Inventory": get_latest_value(latest_balance_sheet, ["Inventory"]),
            "Current Assets": get_latest_value(latest_balance_sheet, ["CurrentAssets"]),
            "Accounts Payable": get_latest_value(latest_balance_sheet, ["AccountsPayable", "PayablesAndAccruedExpenses"]),
            "Current Liabilities": get_latest_value(latest_balance_sheet, ["CurrentLiabilities"]),
            "Total Assets": get_latest_value(latest_balance_sheet, ["TotalAssets"]),
            "Total Liabilities": get_latest_value(
                latest_balance_sheet,
                ["TotalLiabilitiesNetMinorityInterest", "TotalLiabilities"],
            ),
            "Description": get_info_value(info, ["longBusinessSummary"]),
            "Depreciation": get_ttm_value(
                quarterly_cashflow,
                [
                    "DepreciationAndAmortization",
                    "DepreciationAmortizationDepletion",
                    "Depreciation",
                    "Amortization",
                ],
            ),
            "OCF": get_ttm_value(
                quarterly_cashflow,
                ["OperatingCashFlow", "CashFlowFromContinuingOperatingActivities"],
            ),
        }

        return {key: _clean_excel_value(value) for key, value in data.items()}, messages

    except Exception as exc:
        messages.append(f"Error fetching data for {ticker}: {exc}")
        return None, messages
