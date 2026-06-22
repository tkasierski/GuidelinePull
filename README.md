# GuidelinePull

A Streamlit app for uploading a guideline-company Excel template, reading tickers from the template, pulling financial data from Yahoo Finance, filling the workbook, and downloading the completed Excel file.

## Template assumptions

The uploaded workbook must include an `Info` sheet.

Ticker inputs are read from:

```text
Info!A8:A17
```

The app writes pulled data back into the same rows and preserves the workbook structure, formulas, and formatting where possible.

The app also writes company descriptions to a `Descriptions` sheet.

## Streamlit deployment

Use these settings in Streamlit Community Cloud:

```text
Repository: tkasierski/GuidelinePull
Branch: main
Main file path: streamlit_app.py
```

## Local usage

```bash
git clone <repo-url>
cd GuidelinePull
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Data notes

Yahoo Finance data may be missing, stale, revised, or unavailable for certain companies or line items. Missing fields are written as `N/A` so the workbook remains usable.