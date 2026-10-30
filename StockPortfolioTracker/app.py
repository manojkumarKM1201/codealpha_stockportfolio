"""
Stock Portfolio Tracker - Streamlit Application.
CodeAlpha Python Programming Internship - Task 2.

A professional, beginner-friendly financial dashboard supporting:
- Persistent SQLite storage for BUY and SELL transactions
- Weighted-Average Cost Basis (WACB) accounting
- Optional Live / Cached Market Data (Yahoo Finance, Alpha Vantage, Finnhub)
- Complete Offline Mode with Manual Price fallback
- Interactive Plotly visualizations and CSV/TXT exports
"""

from datetime import date, datetime
import os
import io
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

from src.database import (
    init_db,
    add_transaction,
    get_transaction,
    update_transaction,
    delete_transaction,
    get_all_transactions,
    get_distinct_symbols,
    get_holding_quantity,
    backup_database,
)
from src.calculations import HoldingSummary, PortfolioSummary
from src.portfolio import (
    get_all_portfolio_holdings,
    get_active_holdings,
    get_closed_holdings,
    get_portfolio_overview,
    holdings_to_dataframe,
    transactions_to_dataframe,
)
from src.market_data import MarketDataService, DEFAULT_CACHE_TTL
from src.validators import ValidationError
from src.exports import (
    export_holdings_to_csv,
    export_transactions_to_csv,
    export_portfolio_summary_to_csv,
    generate_portfolio_summary_txt,
)

# Page configuration
st.set_page_config(
    page_title="Stock Portfolio Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database schema
init_db()

# Session State Initialization
if "market_service" not in st.session_state:
    st.session_state.market_service = MarketDataService()

if "currency" not in st.session_state:
    st.session_state.currency = os.environ.get("DEFAULT_CURRENCY", "$")

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None


def format_currency(val: float | None, currency: str = "$") -> str:
    """Format floating point numbers as currency."""
    if val is None or pd.isna(val):
        return "N/A"
    return f"{currency}{val:,.2f}"


def format_percent(val: float | None) -> str:
    """Format percentage with +/- sign."""
    if val is None or pd.isna(val):
        return "N/A"
    return f"{val:+.2f}%"


# ==============================================================================
# SIDEBAR NAVIGATION & SETTINGS
# ==============================================================================
with st.sidebar:
    st.title("📈 Portfolio Tracker")
    st.caption("CodeAlpha Python Internship — Task 2")
    st.divider()

    menu = st.radio(
        "Navigation",
        [
            "📊 Dashboard Overview",
            "💼 Holdings Management",
            "➕ Add Transaction",
            "📜 Transaction History",
            "📥 Reports & Settings",
        ],
        index=0,
    )

    st.divider()
    st.subheader("⚙️ Market Data Settings")

    current_provider = st.session_state.market_service.provider_name
    provider_options = ["YFINANCE", "ALPHA_VANTAGE", "FINNHUB", "OFFLINE"]
    default_idx = provider_options.index(current_provider) if current_provider in provider_options else 0

    def on_provider_change():
        chosen = st.session_state.get("provider_choice")
        if chosen:
            st.session_state.market_service.set_provider(chosen)

    selected_provider = st.selectbox(
        "Data Provider",
        provider_options,
        index=default_idx,
        key="provider_choice",
        on_change=on_provider_change,
        help="Choose between live external market data or completely offline manual tracking.",
    )

    # Provider status banner
    if selected_provider == "OFFLINE":
        st.info("🔒 **Offline Mode**: No network calls. Manual prices used.")
    elif selected_provider == "YFINANCE":
        st.success("🟢 **Yahoo Finance**: Free live/delayed data without API key.")
    elif selected_provider == "ALPHA_VANTAGE":
        has_key = bool(os.environ.get("ALPHA_VANTAGE_API_KEY"))
        if has_key:
            st.success("🟢 **Alpha Vantage**: API Key configured.")
        else:
            st.warning("⚠️ **Alpha Vantage**: Missing API key in .env.")
    elif selected_provider == "FINNHUB":
        has_key = bool(os.environ.get("FINNHUB_API_KEY"))
        if has_key:
            st.success("🟢 **Finnhub**: API Key configured.")
        else:
            st.warning("⚠️ **Finnhub**: Missing API key in .env.")

    currency_options = ["$", "€", "£", "₹", "¥", "A$", "C$"]
    curr_idx = currency_options.index(st.session_state.currency) if st.session_state.currency in currency_options else 0
    st.session_state.currency = st.selectbox("Display Currency", currency_options, index=curr_idx)

    if st.button("🔄 Force Price Refresh", use_container_width=True):
        st.session_state.market_service.cache.clear()
        st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
        st.success("Cache cleared & prices refreshed!")
        st.rerun()

    if st.session_state.last_refresh:
        st.caption(f"Last forced refresh: {st.session_state.last_refresh}")


# Helper to get current prices for active symbols
def fetch_current_prices_dict(symbols: list[str]) -> dict:
    if not symbols:
        return {}
    return st.session_state.market_service.get_price_dict_for_symbols(symbols)


# ==============================================================================
# PAGE 1: DASHBOARD OVERVIEW
# ==============================================================================
if menu == "📊 Dashboard Overview":
    st.title("📊 Portfolio Dashboard")
    st.caption("Real-time portfolio valuation, allocation metrics, and performance analytics.")

    symbols = get_distinct_symbols()
    price_dict = fetch_current_prices_dict(symbols)
    overview = get_portfolio_overview(price_data=price_dict)
    active_holdings = get_active_holdings(price_data=price_dict)

    curr = st.session_state.currency

    # Top Metric KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Invested Cost Basis",
            value=format_currency(overview.total_invested_cost_basis, curr),
            help="Total purchase cost basis of currently open stock positions.",
        )
    with col2:
        st.metric(
            label="Current Market Value",
            value=format_currency(overview.total_market_value, curr),
            delta=(
                format_currency(overview.total_unrealized_pnl, curr)
                if overview.holdings_with_price_count > 0
                else None
            ),
            help="Sum of (quantity * latest available market price) for active holdings.",
        )
    with col3:
        pnl_delta = format_percent(overview.overall_unrealized_return_pct)
        st.metric(
            label="Unrealized P&L",
            value=format_currency(overview.total_unrealized_pnl, curr),
            delta=pnl_delta if overview.total_invested_cost_basis > 0 else None,
            help="Unrealized profit or loss across currently open positions.",
        )
    with col4:
        st.metric(
            label="Realized P&L",
            value=format_currency(overview.total_realized_pnl, curr),
            help="Cumulative profit/loss locked in from closed and partial sales (net of fees).",
        )

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric(
            label="Net Total P&L",
            value=format_currency(overview.total_net_pnl, curr),
            help="Realized P&L + Unrealized P&L.",
        )
    with col6:
        st.metric(
            label="Stocks Held",
            value=str(overview.distinct_stocks_count),
            help="Number of distinct stock symbols currently held.",
        )
    with col7:
        st.metric(
            label="Total Transactions",
            value=str(overview.total_transactions_count),
            help="Total recorded BUY and SELL transactions in the database.",
        )
    with col8:
        st.metric(
            label="Total Fees Paid",
            value=format_currency(overview.total_fees_paid, curr),
            help="Total brokerage and transaction fees paid over all trades.",
        )

    # Status callouts
    if overview.holdings_missing_price_count > 0:
        st.warning(
            f"ℹ️ **Notice**: {overview.holdings_missing_price_count} holding(s) do not have a live market price. "
            "Their market value is excluded to prevent fabricated returns. "
            "You can supply manual prices in **Holdings Management**."
        )

    st.divider()

    # Empty State Check
    if not active_holdings:
        st.info(
            "👋 **No active stock positions found.** "
            "Navigate to **➕ Add Transaction** in the sidebar to record your first stock purchase."
        )
    else:
        # Visual Analytics Charts
        st.subheader("📈 Interactive Portfolio Visualizations")

        df_active = holdings_to_dataframe(active_holdings)

        tab1, tab2, tab3 = st.tabs(
            ["🥧 Portfolio Allocation", "📊 Cost vs. Market Value", "💰 Profit & Loss by Stock"]
        )

        with tab1:
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                # Allocation by Market Value (or Cost Basis if market value not priced)
                val_col = "Market Value" if df_active["Market Value"].notna().any() else "Total Cost Basis"
                fig_alloc = px.pie(
                    df_active,
                    names="Symbol",
                    values=val_col,
                    title=f"Asset Allocation by {val_col}",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Prism,
                )
                fig_alloc.update_traces(textposition="inside", textinfo="percent+label")
                fig_alloc.update_layout(margin=dict(t=50, b=20, l=20, r=20))
                st.plotly_chart(fig_alloc, use_container_width=True)

            with col_chart2:
                # Share count distribution
                fig_qty = px.bar(
                    df_active,
                    x="Symbol",
                    y="Quantity Owned",
                    title="Shares Owned Distribution",
                    color="Symbol",
                    text="Quantity Owned",
                )
                fig_qty.update_traces(texttemplate="%{text:.2f}", textposition="outside")
                fig_qty.update_layout(showlegend=False, margin=dict(t=50, b=20, l=20, r=20))
                st.plotly_chart(fig_qty, use_container_width=True)

        with tab2:
            # Grouped Bar Chart: Cost Basis vs Market Value
            fig_compare = go.Figure()
            fig_compare.add_trace(
                go.Bar(
                    x=df_active["Symbol"],
                    y=df_active["Total Cost Basis"],
                    name="Cost Basis (Invested)",
                    marker_color="#2b5c8f",
                )
            )
            fig_compare.add_trace(
                go.Bar(
                    x=df_active["Symbol"],
                    y=df_active["Market Value"].fillna(0),
                    name="Current Market Value",
                    marker_color="#2ecc71",
                )
            )
            fig_compare.update_layout(
                barmode="group",
                title=f"Cost Basis vs. Market Value ({curr})",
                xaxis_title="Stock Symbol",
                yaxis_title=f"Value ({curr})",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(t=50, b=20, l=20, r=20),
            )
            st.plotly_chart(fig_compare, use_container_width=True)

        with tab3:
            # Unrealized P&L Bar Chart with colored bars
            pnl_series = df_active["Unrealized P&L"].fillna(0)
            colors = ["#2ecc71" if x >= 0 else "#e74c3c" for x in pnl_series]

            fig_pnl = go.Figure(
                go.Bar(
                    x=df_active["Symbol"],
                    y=pnl_series,
                    marker_color=colors,
                    text=[f"{curr}{v:,.2f}" for v in pnl_series],
                    textposition="auto",
                )
            )
            fig_pnl.update_layout(
                title=f"Unrealized Profit & Loss by Holding ({curr})",
                xaxis_title="Stock Symbol",
                yaxis_title=f"Unrealized P&L ({curr})",
                margin=dict(t=50, b=20, l=20, r=20),
            )
            st.plotly_chart(fig_pnl, use_container_width=True)


# ==============================================================================
# PAGE 2: HOLDINGS MANAGEMENT
# ==============================================================================
elif menu == "💼 Holdings Management":
    st.title("💼 Current Portfolio Holdings")
    st.caption("Review active positions, cost basis calculations, and configure manual price overrides.")

    symbols = get_distinct_symbols()
    price_dict = fetch_current_prices_dict(symbols)
    active_holdings = get_active_holdings(price_data=price_dict)
    closed_holdings = get_closed_holdings(price_data=price_dict)
    curr = st.session_state.currency

    if not active_holdings and not closed_holdings:
        st.info("No holdings found. Add a transaction to see holdings.")
    else:
        if active_holdings:
            st.subheader(f"Active Positions ({len(active_holdings)})")
            df_active = holdings_to_dataframe(active_holdings)

            # Display formatted dataframe
            display_df = df_active.copy()
            display_df["Avg Purchase Price"] = display_df["Avg Purchase Price"].map(lambda x: format_currency(x, curr))
            display_df["Total Cost Basis"] = display_df["Total Cost Basis"].map(lambda x: format_currency(x, curr))
            display_df["Latest Price"] = display_df["Latest Price"].map(lambda x: format_currency(x, curr))
            display_df["Market Value"] = display_df["Market Value"].map(lambda x: format_currency(x, curr))
            display_df["Unrealized P&L"] = display_df["Unrealized P&L"].map(lambda x: format_currency(x, curr))
            display_df["Return %"] = display_df["Return %"].map(format_percent)
            display_df["Realized P&L"] = display_df["Realized P&L"].map(lambda x: format_currency(x, curr))

            st.dataframe(display_df, use_container_width=True, hide_index=True)

            # Manual Price Override Section
            st.divider()
            with st.expander("✏️ Manual Price Fallback & Overrides", expanded=False):
                st.write(
                    "You can enter manual stock prices here. This is especially useful in **Offline Mode** "
                    "or if an external API symbol lookup fails."
                )
                col_p1, col_p2, col_p3 = st.columns([2, 2, 1])
                with col_p1:
                    override_symbol = st.selectbox(
                        "Stock Symbol",
                        [h.symbol for h in active_holdings],
                        key="override_sym",
                    )
                with col_p2:
                    override_price = st.number_input(
                        f"Price per share ({curr})",
                        min_value=0.01,
                        step=0.5,
                        format="%.4f",
                        key="override_val",
                    )
                with col_p3:
                    st.write("")
                    st.write("")
                    if st.button("Set Price", use_container_width=True):
                        st.session_state.market_service.set_manual_price(override_symbol, override_price)
                        st.success(f"Manual price for {override_symbol} set to {curr}{override_price:,.2f}!")
                        st.rerun()

                if st.button("Clear All Manual Price Overrides"):
                    st.session_state.market_service.clear_manual_price()
                    st.info("Cleared all manual price overrides.")
                    st.rerun()

        # Closed Holdings Expander
        if closed_holdings:
            st.divider()
            with st.expander(f"📦 Closed Positions ({len(closed_holdings)})", expanded=False):
                st.write("Positions that have been completely sold off:")
                df_closed = holdings_to_dataframe(closed_holdings)
                disp_closed = df_closed[["Symbol", "Company Name", "Realized P&L", "Price Source"]].copy()
                disp_closed["Realized P&L"] = disp_closed["Realized P&L"].map(lambda x: format_currency(x, curr))
                st.dataframe(disp_closed, use_container_width=True, hide_index=True)


# ==============================================================================
# PAGE 3: ADD TRANSACTION
# ==============================================================================
elif menu == "➕ Add Transaction":
    st.title("➕ Record Stock Transaction")
    st.caption("Record stock purchases (BUY) or sales (SELL) with comprehensive input validation.")

    curr = st.session_state.currency

    with st.form("transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            symbol_input = st.text_input("Stock Symbol (Ticker) *", placeholder="e.g. AAPL, MSFT, BRK.B").strip().upper()
            company_input = st.text_input("Company Name (Optional)", placeholder="e.g. Apple Inc.")
            tx_type = st.radio("Transaction Type *", ["BUY", "SELL"], horizontal=True)

        with col2:
            quantity_input = st.number_input("Share Quantity *", min_value=0.0001, step=1.0, format="%.4f", value=1.0)
            price_input = st.number_input(f"Price per Share ({curr}) *", min_value=0.0, step=1.0, format="%.4f", value=100.0)
            fees_input = st.number_input(f"Brokerage / Transaction Fees ({curr})", min_value=0.0, step=0.5, format="%.2f", value=0.0)

        col3, col4 = st.columns(2)
        with col3:
            date_input = st.date_input("Transaction Date *", value=date.today(), max_value=date.today())
        with col4:
            notes_input = st.text_input("Notes (Optional)", placeholder="e.g. Rebalancing, DCA purchase")

        # Dynamic validation feedback for SELL
        if tx_type == "SELL" and symbol_input:
            available_qty = get_holding_quantity(symbol_input)
            st.info(f"📊 Currently owned shares of **{symbol_input}**: **{available_qty:g}**")
            if quantity_input > available_qty:
                st.error(f"❌ Error: You cannot sell {quantity_input:g} shares because you only own {available_qty:g} shares.")

        submitted = st.form_submit_button("💾 Save Transaction", use_container_width=True)

        if submitted:
            try:
                new_id = add_transaction(
                    {
                        "symbol": symbol_input,
                        "company_name": company_input,
                        "transaction_type": tx_type,
                        "quantity": quantity_input,
                        "price": price_input,
                        "fees": fees_input,
                        "date": date_input.strftime("%Y-%m-%d"),
                        "notes": notes_input,
                    }
                )
                st.success(f"✅ Successfully recorded {tx_type} transaction for {symbol_input} (Transaction #{new_id})!")
            except ValidationError as ve:
                st.error(f"❌ Validation Error: {ve}")
            except Exception as e:
                st.error(f"❌ Unexpected Error: {str(e)}")


# ==============================================================================
# PAGE 4: TRANSACTION HISTORY
# ==============================================================================
elif menu == "📜 Transaction History":
    st.title("📜 Transaction History")
    st.caption("Search, filter, edit, or delete past stock trades.")

    all_symbols = ["All"] + get_distinct_symbols()
    curr = st.session_state.currency

    # Filtering Bar
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    with f_col1:
        filter_symbol = st.selectbox("Filter Symbol", all_symbols)
    with f_col2:
        filter_type = st.selectbox("Filter Type", ["All", "BUY", "SELL"])
    with f_col3:
        filter_start = st.date_input("Start Date", value=None)
    with f_col4:
        filter_end = st.date_input("End Date", value=None)

    sym_param = None if filter_symbol == "All" else filter_symbol
    type_param = None if filter_type == "All" else filter_type
    start_param = filter_start.strftime("%Y-%m-%d") if filter_start else None
    end_param = filter_end.strftime("%Y-%m-%d") if filter_end else None

    transactions = get_all_transactions(
        symbol=sym_param,
        tx_type=type_param,
        start_date=start_param,
        end_date=end_param,
        order_by_desc=True,
    )

    if not transactions:
        st.info("No transactions match the selected filter criteria.")
    else:
        df_tx = transactions_to_dataframe(transactions)
        disp_tx = df_tx.copy()
        disp_tx["Price"] = disp_tx["Price"].map(lambda x: format_currency(x, curr))
        disp_tx["Fees"] = disp_tx["Fees"].map(lambda x: format_currency(x, curr))
        disp_tx["Total Value"] = disp_tx["Total Value"].map(lambda x: format_currency(x, curr))

        st.dataframe(disp_tx, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("🛠️ Manage / Edit / Delete Transaction")

        tx_ids = [tx["id"] for tx in transactions]
        selected_tx_id = st.selectbox(
            "Select Transaction ID to modify",
            tx_ids,
            format_func=lambda x: f"ID #{x} — {next(t['transaction_date'] + ' ' + t['transaction_type'] + ' ' + str(t['quantity']) + ' ' + t['symbol'] for t in transactions if t['id'] == x)}",
        )

        target_tx = get_transaction(selected_tx_id)

        if target_tx:
            tab_edit, tab_delete = st.tabs(["✏️ Edit Transaction", "🗑️ Delete Transaction"])

            with tab_edit:
                with st.form(f"edit_form_{selected_tx_id}"):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        e_symbol = st.text_input("Symbol", value=target_tx["symbol"]).strip().upper()
                        e_company = st.text_input("Company", value=target_tx.get("company_name") or "")
                        e_type = st.radio("Type", ["BUY", "SELL"], index=0 if target_tx["transaction_type"] == "BUY" else 1)
                    with e_col2:
                        e_qty = st.number_input("Quantity", min_value=0.0001, value=float(target_tx["quantity"]), step=1.0)
                        e_price = st.number_input("Price", min_value=0.0, value=float(target_tx["price"]), step=1.0)
                        e_fees = st.number_input("Fees", min_value=0.0, value=float(target_tx["fees"]), step=0.5)

                    parsed_date = datetime.strptime(target_tx["transaction_date"], "%Y-%m-%d").date()
                    e_date = st.date_input("Date", value=parsed_date, max_value=date.today())
                    e_notes = st.text_input("Notes", value=target_tx.get("notes") or "")

                    if st.form_submit_button("Update Transaction", use_container_width=True):
                        try:
                            update_transaction(
                                selected_tx_id,
                                {
                                    "symbol": e_symbol,
                                    "company_name": e_company,
                                    "transaction_type": e_type,
                                    "quantity": e_qty,
                                    "price": e_price,
                                    "fees": e_fees,
                                    "date": e_date.strftime("%Y-%m-%d"),
                                    "notes": e_notes,
                                },
                            )
                            st.success(f"Transaction #{selected_tx_id} successfully updated!")
                            st.rerun()
                        except ValidationError as ve:
                            st.error(f"Cannot update: {ve}")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

            with tab_delete:
                st.warning(f"Are you sure you want to delete Transaction #{selected_tx_id}?")
                confirm_del = st.checkbox(f"Yes, I confirm I want to permanently delete transaction #{selected_tx_id}")
                if st.button("Delete Transaction", type="primary", disabled=not confirm_del):
                    try:
                        delete_transaction(selected_tx_id)
                        st.success(f"Transaction #{selected_tx_id} was deleted.")
                        st.rerun()
                    except ValidationError as ve:
                        st.error(f"Cannot delete: {ve}")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")


# ==============================================================================
# PAGE 5: REPORTS & SETTINGS
# ==============================================================================
elif menu == "📥 Reports & Settings":
    st.title("📥 Reports, Exports & Settings")
    st.caption("Export your portfolio holdings and trade history, download database backups, and inspect methodology.")

    symbols = get_distinct_symbols()
    price_dict = fetch_current_prices_dict(symbols)
    all_holdings = get_all_portfolio_holdings(price_data=price_dict)
    overview = get_portfolio_overview(price_data=price_dict)
    all_txs = get_all_transactions()
    curr = st.session_state.currency

    st.subheader("📊 Export Data & Reports")
    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        st.write("##### 📄 CSV Spreadsheets")
        # Holdings CSV
        holdings_csv = export_holdings_to_csv(all_holdings)
        st.download_button(
            label="📥 Download Holdings (CSV)",
            data=holdings_csv,
            file_name=f"portfolio_holdings_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

        # Transactions CSV
        tx_csv = export_transactions_to_csv(all_txs)
        st.download_button(
            label="📥 Download Transaction History (CSV)",
            data=tx_csv,
            file_name=f"transaction_history_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

        # Summary CSV
        summary_csv = export_portfolio_summary_to_csv(overview, currency=curr)
        st.download_button(
            label="📥 Download Portfolio Summary (CSV)",
            data=summary_csv,
            file_name=f"portfolio_summary_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_exp2:
        st.write("##### 📑 Executive Performance Summary")
        txt_report = generate_portfolio_summary_txt(overview, all_holdings, currency=curr)
        st.download_button(
            label="📥 Download Executive Report (TXT)",
            data=txt_report,
            file_name=f"portfolio_executive_report_{date.today()}.txt",
            mime="text/plain",
            use_container_width=True,
        )

        st.write("##### 🗄️ Database Backup")
        # Backup SQLite database
        backup_bytes = io.BytesIO()
        db_file = os.environ.get("DATABASE_PATH", os.path.join("data", "portfolio.db"))
        if os.path.exists(db_file):
            with open(db_file, "rb") as f:
                backup_bytes.write(f.read())
            backup_bytes.seek(0)
            st.download_button(
                label="📥 Download Database Backup (.db)",
                data=backup_bytes,
                file_name=f"portfolio_backup_{date.today()}.db",
                mime="application/x-sqlite3",
                use_container_width=True,
            )
        else:
            st.info("No database file created yet.")

    st.divider()

    st.subheader("📚 Calculation Methodology & Documentation")
    with st.expander("📖 Financial Calculations Guide", expanded=False):
        st.markdown(
            r"""
            ### Weighted-Average Cost Basis (WACB)
            This tracker calculates portfolio performance using the standard **Weighted-Average Cost Basis** method:
            
            1. **Purchase Cost**:
               $$\text{Total Cost} = (\text{Quantity} \times \text{Price}) + \text{Brokerage Fees}$$
            
            2. **Weighted Average Purchase Price**:
               $$\text{Average Price} = \frac{\text{Remaining Cost Basis}}{\text{Current Shares Held}}$$
            
            3. **Partial Sales & Cost Basis Reduction**:
               When selling shares, the cost basis is reduced strictly proportionally:
               $$\text{Cost Basis Sold} = \text{Sold Quantity} \times \text{Average Price}$$
               $$\text{Remaining Cost Basis} = \text{Previous Cost Basis} - \text{Cost Basis Sold}$$
            
            4. **Realized Profit / Loss**:
               $$\text{Realized P&L} = (\text{Sold Quantity} \times \text{Sale Price}) - \text{Sale Fee} - \text{Cost Basis Sold}$$
            
            5. **Unrealized Profit / Loss**:
               $$\text{Unrealized P&L} = (\text{Current Shares} \times \text{Market Price}) - \text{Remaining Cost Basis}$$
            
            6. **Percentage Return**:
               $$\text{Return \%} = \frac{\text{Profit or Loss}}{\text{Invested Cost Basis}} \times 100$$
               *(Safely returns 0.0% when cost basis is zero)*
            """
        )

    with st.expander("🔑 Market Data API Configuration Guide", expanded=False):
        st.markdown(
            """
            ### How to Configure External Market Data Providers:
            
            1. **Yahoo Finance (Default)**:
               - Requires **no API key**.
               - Automatically fetches live or delayed market prices.
            
            2. **Alpha Vantage**:
               - Get a free API key at [Alpha Vantage](https://www.alphavantage.co/support/#api-key).
               - Create a `.env` file in the project root:
                 ```ini
                 MARKET_DATA_PROVIDER=ALPHA_VANTAGE
                 ALPHA_VANTAGE_API_KEY=your_key_here
                 ```
            
            3. **Finnhub**:
               - Get a free API key at [Finnhub](https://finnhub.io/).
               - In `.env`:
                 ```ini
                 MARKET_DATA_PROVIDER=FINNHUB
                 FINNHUB_API_KEY=your_key_here
                 ```
            
            4. **Offline Mode**:
               - Switch to `OFFLINE` in the sidebar or set `MARKET_DATA_PROVIDER=OFFLINE` in `.env`.
               - Enter manual prices whenever desired in **Holdings Management**.
            """
        )
