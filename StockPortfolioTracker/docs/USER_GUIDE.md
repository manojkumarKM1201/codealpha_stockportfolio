# Stock Portfolio Tracker — User Guide
**CodeAlpha Python Programming Internship — Task 2**

---

## 1. Introduction

Welcome to the **Stock Portfolio Tracker**! This application is designed to help you track your stock holdings, manage your investment history, calculate real-time and historical profit or loss using the **Weighted-Average Cost Basis (WACB)** method, and visualize your portfolio allocation.

The tracker works in two primary modes:
1. **Offline Mode**: Operates completely without internet access or external accounts. You enter transactions and provide stock prices manually.
2. **Live-Data Mode**: Automatically queries market data providers (e.g. Yahoo Finance, Alpha Vantage, Finnhub) to obtain live or delayed quotes, caching them for fast, responsive performance.

---

## 2. Getting Started & Launching

To launch the application:
1. Open PowerShell or Command Prompt in the project folder:
   ```powershell
   streamlit run app.py
   ```
2. Your default web browser will open to:
   ```text
   http://localhost:8501
   ```
3. Use the sidebar on the left to navigate between different pages.

---

## 3. Sidebar Navigation & Configuration

The sidebar contains:
- **Navigation Menu**:
  - `📊 Dashboard Overview`: High-level metrics, asset allocation, and interactive charts.
  - `💼 Holdings Management`: Detailed table of active positions, cost basis, and manual price overrides.
  - `➕ Add Transaction`: Input form to record stock purchases and sales.
  - `📜 Transaction History`: Search, filter, edit, or delete past transactions.
  - `📥 Reports & Settings`: Export your data to CSV or TXT, and download database backups.
- **Data Provider Dropdown**:
  - `YFINANCE`: Live/delayed quotes via Yahoo Finance (No API key needed).
  - `ALPHA_VANTAGE`: Live quotes via Alpha Vantage (Requires API key in `.env`).
  - `FINNHUB`: Real-time quotes via Finnhub (Requires API key in `.env`).
  - `OFFLINE`: Pure offline tracking.
- **Display Currency**:
  - Select between `$`, `€`, `£`, `₹`, `¥`, `A$`, or `C$`.
- **Force Price Refresh Button**:
  - Clears in-memory price caches and immediately re-fetches market data.

---

## 4. How to Record Transactions

### Recording a Purchase (BUY)
1. In the sidebar, select **➕ Add Transaction**.
2. Fill in the transaction fields:
   - **Stock Symbol (Ticker)**: The unique stock ticker (e.g. `AAPL`, `MSFT`, `GOOGL`, `BRK.B`).
   - **Company Name (Optional)**: Friendly name (e.g. `Apple Inc.`).
   - **Transaction Type**: Choose **BUY**.
   - **Share Quantity**: Number of shares purchased (e.g., `10`, `0.5` for fractional shares).
   - **Price per Share**: The purchase price per share.
   - **Brokerage / Transaction Fees**: Any commission or exchange fee paid (defaults to `0.00`).
   - **Transaction Date**: The date the trade occurred (cannot be in the future).
   - **Notes (Optional)**: Any notes for your records (e.g. `DCA monthly deposit`).
3. Click **💾 Save Transaction**. A success notification will appear with your transaction ID.

### Recording a Sale (SELL)
1. In the sidebar, select **➕ Add Transaction**.
2. Select **SELL** as the transaction type.
3. Enter the ticker symbol (e.g. `AAPL`).
4. The system automatically inspects your database and displays your currently owned shares.
5. Enter the quantity you wish to sell:
   - **Oversell Protection**: The system will prevent you from submitting a sale quantity greater than the shares you currently own.
6. Enter the sale price and any exit brokerage fees.
7. Click **💾 Save Transaction**.
   - The application will automatically calculate the realized gain or loss, deduct the shares from your holding, and adjust your remaining cost basis proportionally.

---

## 5. Reviewing Holdings & Cost Basis

Navigate to **💼 Holdings Management**:
- **Active Positions**:
  - **Quantity Owned**: Net remaining shares.
  - **Avg Purchase Price**: Weighted average purchase price per share (including buy fees).
  - **Total Cost Basis**: Total capital currently invested in the holding.
  - **Latest Price**: Current market price (or manual override).
  - **Market Value**: Quantity × Latest Price.
  - **Unrealized P&L**: Market Value − Cost Basis.
  - **Return %**: Percentage gain or loss on your active cost basis.
  - **Realized P&L**: Profit or loss locked in from any partial sales of this stock.
  - **Price Source**: Labeled as `LIVE`, `CACHED`, `MANUAL`, or `UNAVAILABLE`.
  - **Price Updated At**: Timestamp of the last successful price update.

### Setting Manual Prices (Offline Fallback)
If you are running in **Offline Mode** or an API does not recognize a ticker:
1. Expand the **✏️ Manual Price Fallback & Overrides** section.
2. Select the stock symbol.
3. Enter the price per share.
4. Click **Set Price**.
5. The dashboard and holdings tables will update immediately using your manual price (clearly labeled `MANUAL`).

### Closed Positions
If you sell all shares of a stock (quantity reaches 0), the stock moves to the **📦 Closed Positions** expander, preserving your full historical realized profit or loss.

---

## 6. Managing Past Transactions

Navigate to **📜 Transaction History**:
- **Filter and Search**:
  - Filter by specific stock symbol.
  - Filter by transaction type (`BUY` or `SELL`).
  - Filter by start and end date.
- **Editing a Transaction**:
  - Select the transaction ID from the dropdown.
  - Modify any fields in the **✏️ Edit Transaction** tab.
  - Click **Update Transaction**.
  - *Integrity Guard*: The system will reject updates if the modification would cause a downstream sell transaction to have a negative balance.
- **Deleting a Transaction**:
  - Switch to the **🗑️ Delete Transaction** tab.
  - Check the confirmation box: `Yes, I confirm I want to permanently delete transaction #...`
  - Click **Delete Transaction**.
  - *Integrity Guard*: You cannot delete a purchase if you later sold those shares without first adjusting or deleting the sale.

---

## 7. Reports and Data Export

Navigate to **📥 Reports & Settings**:
- **Download Holdings (CSV)**: Export current holdings and metrics into a spreadsheet.
- **Download Transaction History (CSV)**: Complete audit log of all historical trades.
- **Download Portfolio Summary (CSV)**: Executive key-value performance summary.
- **Download Executive Report (TXT)**: Formatted plain-text summary suitable for printing or record-keeping.
- **Download Database Backup (.db)**: Full binary snapshot of your SQLite database for safe backups.

---

## 8. Troubleshooting & FAQ

**Q: Why does a stock display "UNAVAILABLE" for its price?**
- In Offline Mode, prices remain unavailable until you set a manual price in Holdings Management.
- In Live Data mode, check that your computer has an active internet connection and that the symbol is a valid ticker recognized by your selected provider (e.g. Yahoo Finance uses `AAPL`, `MSFT`, etc.).

**Q: How are purchase and sale fees handled?**
- **Purchase Fees**: Added to the cost basis of the purchase, increasing your average cost per share.
- **Sale Fees**: Deducted from the gross sale proceeds, reducing your net realized profit (or increasing your realized loss).

**Q: Can I backup and restore my portfolio on another computer?**
- Yes! Download the `.db` backup file from **📥 Reports & Settings**. You can place this file in the `data/portfolio.db` path on another computer running the application.
