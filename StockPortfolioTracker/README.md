# Advanced Stock Portfolio Tracker
**CodeAlpha Python Programming Internship — Task 2**

[![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Streamlit-1.40%2B-FF4B4B.svg)](https://streamlit.io/)
[![Database](https://img.shields.io/badge/SQLite-Persistent-003B57.svg)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A complete, professional, beginner-friendly Stock Portfolio Tracker built in Python. Record stock purchases and sales, monitor portfolio allocation, track real-time valuations, and calculate realized and unrealized profit or loss using the industry-standard **Weighted-Average Cost Basis (WACB)** method.

---

## 📑 Table of Contents
1. [Project Overview](#-project-overview)
2. [Key Features](#-key-features)
3. [Technologies Used](#-technologies-used)
4. [Prerequisites](#-prerequisites)
5. [Installation & Setup (Windows)](#-installation--setup-windows)
6. [Running the Application](#-running-the-application)
7. [Running Automated Tests](#-running-automated-tests)
8. [Configuring External Market Data APIs](#-configuring-external-market-data-apis)
9. [Financial Calculation Methodology](#-financial-calculation-methodology)
10. [Project Structure](#-project-structure)
11. [Known Limitations](#-known-limitations)
12. [GitHub Upload Instructions](#-github-upload-instructions)

---

## 🌟 Project Overview

The **Advanced Stock Portfolio Tracker** is designed for individual investors and students who want clear, reliable portfolio performance metrics without confusing jargon or hidden fees.

The tracker supports two flexible operating modes:
- **Offline Mode**: Enter transactions and provide manual stock prices. Zero external network calls required.
- **Live-Data Mode**: Automatically fetch real-time or delayed market quotes from configurable providers (**Yahoo Finance**, **Alpha Vantage**, **Finnhub**), protected by an in-memory cache to respect rate limits.

---

## ✨ Key Features

- **📊 Comprehensive Financial Dashboard**:
  - Total Invested Capital (Cost Basis)
  - Current Portfolio Market Value
  - Unrealized Profit / Loss & Unrealized Return %
  - Realized Profit / Loss (locked-in gains/losses from partial and full sales)
  - Net Total Profit / Loss
  - Distinct stocks count, total trade count, and total brokerage fees paid
- **📈 Interactive Plotly Visualizations**:
  - Asset Allocation Donut Chart
  - Shares Distribution Bar Chart
  - Investment Cost Basis vs. Current Market Value Grouped Comparison
  - Holding-level Profit & Loss Bar Chart (Green for profits, Red for losses)
- **💼 Robust Holdings Management**:
  - Automatic Weighted-Average Cost Basis updates on every buy
  - Proportional cost-basis reduction on partial sales
  - Closed positions tracking for historical sales
  - Manual price override fallback with explicit source labeling (`LIVE`, `CACHED`, `MANUAL`, `UNAVAILABLE`)
- **🛡️ Data Integrity & Safety**:
  - Overselling prevention: Users cannot sell more shares than they currently own
  - Chronological validation: Editing or deleting past purchases is rejected if it would cause negative downstream balances
  - Parameterized SQLite queries to guard against SQL injection
  - Safe transactional backups via SQLite Backup API
- **📥 Multi-Format Reporting & Export**:
  - Holdings as CSV
  - Transaction History as CSV
  - Executive Portfolio Metrics as CSV
  - Printable Executive Summary as TXT
  - Full SQLite database backup download (.db)

---

## 🧰 Technologies Used

- **Language**: Python 3.11+ (Tested on Python 3.13)
- **User Interface**: Streamlit
- **Data Analysis**: Pandas, NumPy
- **Database**: SQLite3
- **Visualization**: Plotly Express & Plotly Graph Objects
- **Configuration**: python-dotenv
- **Testing**: Pytest (53 comprehensive unit and integration tests)
- **Market Data Adapters**: yfinance, Requests

---

## 📋 Prerequisites

Before installing, ensure you have:
- Windows 10 / 11 (or macOS / Linux)
- Python 3.11 or newer installed and added to your `PATH`
  - Verify by opening PowerShell and running:
    ```powershell
    python --version
    ```

---

## 🚀 Installation & Setup (Windows)

### 1. Clone or Download the Repository
Open PowerShell and navigate to your desired directory:
```powershell
cd c:\path\to\your\projects
git clone https://github.com/your-username/StockPortfolioTracker.git
cd StockPortfolioTracker
```

### 2. Create a Virtual Environment (Recommended)
Creating an isolated virtual environment prevents conflicts with system packages:
```powershell
python -m venv .venv
```

Activate the virtual environment:
```powershell
.venv\Scripts\Activate.ps1
```
*(If PowerShell shows an execution policy restriction, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` in your session first).*

### 3. Install Dependencies
Install all required packages from `requirements.txt`:
```powershell
pip install -r requirements.txt
```

### 4. Create Local Configuration (Optional)
If you wish to configure API keys or change default parameters:
```powershell
copy .env.example .env
```
*(The application works immediately in **OFFLINE** and **YFINANCE** mode without creating or modifying a `.env` file).*

---

## 🖥️ Running the Application

Launch the Streamlit dashboard by running:
```powershell
streamlit run app.py
```
Or run directly through Python:
```powershell
python -m streamlit run app.py
```

Your default web browser will automatically open to `http://localhost:8501`.

---

## 🧪 Running Automated Tests

The project includes an extensive test suite covering:
- Database initialization and schema constraints
- Adding BUY and SELL transactions
- Oversell rejection and chronological balance validation
- Weighted-average cost basis and partial sales
- Realized and unrealized P&L calculations
- Brokerage fee deductions
- Empty portfolio safety (zero division guards)
- Symbol format validation
- Market data API error and rate-limit handling (with mocks)
- CSV and TXT export fidelity

Run all tests with:
```powershell
pytest -v
```
Or using python:
```powershell
python -m pytest tests/ -v
```

All 53 unit and integration tests execute completely offline without requiring internet access or paid API keys.

---

## 🔑 Configuring External Market Data APIs

The application defaults to **Yahoo Finance** (`YFINANCE`), which requires **no API key**.

To use alternative market data providers:
1. Open your `.env` file (copied from `.env.example`).
2. Set the `MARKET_DATA_PROVIDER` variable to one of the supported options:

```ini
# Options: YFINANCE, ALPHA_VANTAGE, FINNHUB, OFFLINE
MARKET_DATA_PROVIDER=YFINANCE

# Optional API Keys:
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
FINNHUB_API_KEY=your_finnhub_key

# Cache duration in seconds (prevents rate limits; default: 300 = 5 minutes)
PRICE_CACHE_TTL_SECONDS=300

# SQLite Database location
DATABASE_PATH=data/portfolio.db

# Display Currency Symbol
DEFAULT_CURRENCY=$
```

> **Security Note**: Never commit your `.env` file or your `data/*.db` files to GitHub. These are already excluded in `.gitignore`.

---

## 📐 Financial Calculation Methodology

### 1. Total Purchase Cost
When purchasing shares, brokerage and transaction fees are capitalized into the initial cost basis:
$$\text{Total Cost} = (\text{Quantity} \times \text{Purchase Price}) + \text{Brokerage Fee}$$

### 2. Weighted-Average Cost Basis (WACB)
When additional shares are bought at different prices, the average price updates dynamically:
$$\text{Average Price} = \frac{\text{Previous Cost Basis} + \text{New Purchase Cost}}{\text{Previous Quantity} + \text{New Quantity}}$$

### 3. Partial and Full Sales
When shares are sold:
1. The cost basis of the shares being sold is deducted proportionally:
   $$\text{Cost Basis Sold} = \text{Sold Quantity} \times \text{Average Price}$$
2. The remaining cost basis is reduced:
   $$\text{Remaining Cost Basis} = \text{Previous Cost Basis} - \text{Cost Basis Sold}$$
3. The average purchase price per share remains unchanged until subsequent purchases are made.
4. If all shares are sold ($\text{Remaining Quantity} = 0$), the remaining cost basis resets to \$0.00.

### 4. Realized Profit / Loss
Locked-in gain or loss upon sale accounts for transaction exit fees:
$$\text{Net Proceeds} = (\text{Sold Quantity} \times \text{Sale Price}) - \text{Sale Fee}$$
$$\text{Realized P&L} = \text{Net Proceeds} - \text{Cost Basis Sold}$$

### 5. Unrealized Profit / Loss
Paper gain or loss for open positions:
$$\text{Market Value} = \text{Current Quantity} \times \text{Latest Available Price}$$
$$\text{Unrealized P&L} = \text{Market Value} - \text{Remaining Cost Basis}$$

### 6. Return Percentage
$$\text{Return \%} = \frac{\text{Profit or Loss}}{\text{Invested Cost Basis}} \times 100$$
*(If invested cost basis is zero, the system safely returns `0.0%` to prevent division-by-zero errors).*

---

## 📁 Project Structure

```text
StockPortfolioTracker/
│
├── app.py                      # Main Streamlit web application
├── requirements.txt            # Project dependencies
├── README.md                   # Complete setup and architecture documentation
├── .gitignore                  # Git exclusions for secrets, databases, and caches
├── .env.example                # Sample environment template
│
├── src/                        # Core application modules
│   ├── __init__.py             # Package marker
│   ├── database.py             # SQLite connection, schema, and transactional CRUD
│   ├── portfolio.py            # Portfolio state, holdings grouping, and dataframes
│   ├── calculations.py         # Financial mathematics (WACB, PnL, fee allocations)
│   ├── market_data.py          # API adapter, in-memory cache, and fallback handlers
│   ├── validators.py           # Input sanitization and portfolio integrity checks
│   └── exports.py              # CSV and TXT report generators
│
├── tests/                      # Automated test suite (53 tests)
│   ├── __init__.py             # Package marker
│   ├── test_app_structure.py   # App compilation and AST structure tests
│   ├── test_database.py        # Database CRUD, integrity, and backup tests
│   ├── test_calculations.py    # WACB, fees, partial sales, and PnL unit tests
│   ├── test_portfolio.py       # Portfolio aggregation and DataFrame tests
│   ├── test_market_data.py     # Cache, mock API responses, and timeout tests
│   ├── test_validators.py      # Input validation and sell limit tests
│   ├── test_exports.py         # CSV & TXT report content fidelity tests
│   └── test_integration.py    # Multi-step end-to-end lifecycle tests
│
├── data/
│   └── .gitkeep                # Retains data directory in git while ignoring .db
│
└── docs/
    └── USER_GUIDE.md           # Step-by-step user instructions & walkthrough
```

---

## ⚠️ Known Limitations

1. **Market Data Latency**: Free market data tiers (Yahoo Finance, Alpha Vantage free tier) provide quotes that may be delayed by 15 minutes or subject to rate limits (e.g. Alpha Vantage allows 5 requests per minute). Use **Offline Mode** or the built-in 5-minute cache to avoid rate limits.
2. **Short Selling**: This application focuses on long holdings (BUY to open, SELL to close). Short selling (selling borrowed shares before buying) is deliberately restricted by the overselling validator.
3. **Currency Conversion**: The tracker supports multiple currency symbols (`$`, `€`, `£`, `₹`, etc.), but assumes all transactions in a single portfolio are recorded in that selected currency. Multi-currency automatic FX conversion is not included in this release.

---

## 📤 GitHub Upload Instructions

Follow these steps to safely push your project to GitHub:

### 1. Initialize Git (if not already initialized)
```powershell
git init
```

### 2. Verify `.gitignore`
Make sure `.gitignore` excludes your virtual environment, `.env`, and database files:
```powershell
git status
```
Ensure you do NOT see `.venv/`, `.env`, or `portfolio.db` in untracked files.

### 3. Stage and Commit Files
```powershell
git add .
git commit -m "Initial commit: Complete CodeAlpha Stock Portfolio Tracker"
```

### 4. Create Repository on GitHub & Push
1. Go to [github.com/new](https://github.com/new) and create a repository named `CodeAlpha_StockPortfolioTracker`.
2. Do not check "Add a README" or ".gitignore" on GitHub (we already created them).
3. Run the following commands:
```powershell
git branch -M main
git remote add origin https://github.com/your-username/CodeAlpha_StockPortfolioTracker.git
git push -u origin main
```

---

## 📄 License
This project is developed for educational purposes under the **CodeAlpha Python Programming Internship**. Licensed under the [MIT License](LICENSE).
