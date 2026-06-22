from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from guideline_pull.workbook import extract_tickers_from_workbook, fill_workbook


st.set_page_config(page_title="Guideline Pull", layout="wide")

st.title("Guideline Pull")
st.write(
    "Upload a guideline-company Excel template. The app reads tickers from `Info!A8:A17`, "
    "pulls Yahoo Finance data, fills the template, and returns a completed workbook."
)

uploaded_file = st.file_uploader("Upload template workbook", type=["xlsx"])

if uploaded_file is None:
    st.info("Upload an `.xlsx` template to begin.")
    st.stop()

try:
    tickers = extract_tickers_from_workbook(uploaded_file)
except Exception as exc:
    st.error(f"Template error: {exc}")
    st.stop()

if not tickers:
    st.warning("No tickers found in `Info!A8:A17`.")
    st.stop()

st.subheader("Tickers found")
st.write(", ".join(tickers))

st.caption("Data source: Yahoo Finance via yfinance. Missing fields will be written as N/A.")

if st.button("Fill template", type="primary"):
    with st.spinner("Fetching financial data and filling workbook..."):
        try:
            uploaded_file.seek(0)
            workbook_bytes, data_by_ticker, logs = fill_workbook(uploaded_file)
        except Exception as exc:
            st.error(f"Error: {exc}")
            st.stop()

    successful = [ticker for ticker, values in data_by_ticker.items() if values]
    failed = [ticker for ticker, values in data_by_ticker.items() if not values]

    st.success("Workbook completed.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Successful tickers")
        st.write(", ".join(successful) if successful else "None")
    with col2:
        st.subheader("Failed tickers")
        st.write(", ".join(failed) if failed else "None")

    if successful:
        preview_rows = []
        for ticker in successful:
            values = data_by_ticker[ticker]
            preview_rows.append(
                {
                    "Ticker": ticker,
                    "Name": values.get("Name"),
                    "Price per Share": values.get("Price per Share"),
                    "LTM Revenue": values.get("LTM Revenue"),
                    "LTM EBITDA": values.get("LTM EBITDA"),
                    "Total Debt": values.get("Total Debt"),
                    "Cash": values.get("Cash"),
                }
            )
        st.subheader("Preview")
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

    with st.expander("Run log"):
        st.text("\n".join(logs) if logs else "No log messages.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        "Download completed workbook",
        data=BytesIO(workbook_bytes),
        file_name=f"Guideline_Pull_completed_{timestamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info("Click Fill template to pull data and generate the completed workbook.")
