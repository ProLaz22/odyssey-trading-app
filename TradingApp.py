import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
import json
import os
import time
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import random

# --- Page Configuration ---
st.set_page_config(
    page_title="Odyssey Trading Terminal",
    page_icon="🚀",
    layout="wide"
)

# --- App Title ---
st.title("🚀 Odyssey Trading Terminal")

# --- Helper Functions (Backend Logic) ---
def is_market_open():
    """Checks if the NYSE market is open."""
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    # Market is open 9:30 AM to 4:00 PM ET, Mon-Fri
    return not (now.weekday() > 4 or now.hour < 9 or (now.hour == 9 and now.minute < 30) or now.hour >= 16)

def get_current_price(ticker):
    """Fetches the current market price of a stock."""
    try:
        stock = yf.Ticker(ticker)
        price = stock.info.get('regularMarketPrice')
        # Fallback to previous close if live price isn't available
        return price if price else stock.info.get('previousClose')
    except Exception:
        return None

def save_state():
    """Saves the session state to a JSON file."""
    state_to_save = {key: val for key, val in st.session_state.items() if isinstance(val, (int, float, str, list, dict, bool))}
    with open("portfolio.json", 'w') as f:
        json.dump(state_to_save, f, indent=4)
    st.toast("Session Saved!", icon="💾")

def load_state():
    """Loads the session state from a JSON file."""
    if os.path.exists("portfolio.json"):
        with open("portfolio.json", 'r') as f:
            data = json.load(f)
            for key, val in data.items():
                st.session_state[key] = val
        st.toast("Session Loaded!", icon="📂")

# --- Initialize Session State ---
if 'cash_balance' not in st.session_state:
    st.session_state.cash_balance = 100000.0
    st.session_state.portfolio = {}
    st.session_state.trade_history = []
    st.session_state.watchlist = ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
    st.session_state.main_ticker = "NVDA"
    st.session_state.show_order_form = False

# --- Automatic Order Checking ---
def check_orders():
    if not is_market_open(): return
    for ticker in list(st.session_state.portfolio):
        if ticker not in st.session_state.portfolio: continue
        data = st.session_state.portfolio[ticker]
        price = get_current_price(ticker)
        if not price: continue
        
        reason = None
        if data.get('stop_loss') and price <= data['stop_loss']:
            reason = "Stop-Loss"
        elif data.get('take_profit') and price >= data['take_profit']:
            reason = "Take-Profit"
        
        if reason:
            st.toast(f"{reason} triggered for {ticker}!", icon="🔔")
            shares_to_sell = data['shares']
            proceeds = price * shares_to_sell
            avg_price = st.session_state.portfolio[ticker]['avg_price']
            profit_loss = (price - avg_price) * shares_to_sell
            st.session_state.cash_balance += proceeds
            del st.session_state.portfolio[ticker]
            st.session_state.trade_history.append({'timestamp': datetime.now().isoformat(), 'type': 'SELL', 'ticker': ticker, 'shares': shares_to_sell, 'price': price, 'profit_loss': profit_loss})
            st.rerun()

# --- Main two-column layout ---
col1, col2 = st.columns([1, 2])

# --- COLUMN 1: Control Panel ---
with col1:
    st.header("⚙️ Control Panel")
    
    with st.container(border=True):
        st.subheader("💰 Account")
        st.metric("Cash Balance", f"${st.session_state.cash_balance:,.2f}")
        save_col, load_col = st.columns(2)
        if save_col.button("Save Session", use_container_width=True): save_state()
        if load_col.button("Load Session", use_container_width=True): load_state(); st.rerun()

    with st.container(border=True):
        st.subheader("📈 Market Info")
        st.session_state.main_ticker = st.text_input("Stock Ticker", st.session_state.main_ticker).upper()
        current_price = get_current_price(st.session_state.main_ticker)
        st.session_state.current_price_for_calc = current_price if current_price else 0.0
        
        price_col, market_status_col = st.columns(2)
        price_col.metric("Current Price", f"${current_price:,.2f}" if current_price else "N/A")
        if is_market_open():
            market_status_col.success("Market is Open")
        else:
            market_status_col.error("Market is Closed")

    with st.expander("▶️ Place New Order"):
        st.subheader("New Order")
        shares_input = st.number_input("Shares", min_value=1, step=1, key="shares")

        def update_ticks_from_price(kind):
            price_key, ticks_key = f"{kind}_price_form", f"{kind}_ticks_form"
            if st.session_state.get(price_key, 0) > 0 and st.session_state.current_price_for_calc > 0:
                delta = st.session_state[price_key] - st.session_state.current_price_for_calc
                st.session_state[ticks_key] = int(round(delta / 0.01))
        def update_price_from_ticks(kind):
            price_key, ticks_key = f"{kind}_price_form", f"{kind}_ticks_form"
            if st.session_state.current_price_for_calc > 0:
                delta = st.session_state.get(ticks_key, 0) * 0.01
                st.session_state[price_key] = round(st.session_state.current_price_for_calc + delta, 2)
        
        tp_enabled = st.checkbox("Take profit")
        if tp_enabled:
            tp_col1, tp_col2 = st.columns(2)
            tp_col1.number_input("Price", key="tp_price_form", step=0.01, format="%.2f", on_change=update_ticks_from_price, args=('tp',))
            tp_col2.number_input("Ticks", key="tp_ticks_form", step=1, on_change=update_price_from_ticks, args=('tp',))

        sl_enabled = st.checkbox("Stop loss")
        if sl_enabled:
            sl_col1, sl_col2 = st.columns(2)
            sl_col1.number_input("Price", key="sl_price_form", step=0.01, format="%.2f", on_change=update_ticks_from_price, args=('sl',))
            sl_col2.number_input("Ticks", key="sl_ticks_form", step=1, on_change=update_price_from_ticks, args=('sl',))

        buy_col, sell_col = st.columns(2)
        if buy_col.button("Submit Buy Order", use_container_width=True):
            if not is_market_open(): st.error("Market is closed.")
            else:
                price = st.session_state.current_price_for_calc
                sl_price = st.session_state.get('sl_price_form') if sl_enabled else None
                tp_price = st.session_state.get('tp_price_form') if tp_enabled else None
                valid_trade = True
                if sl_enabled and sl_price >= price: st.error("Stop-Loss must be below current price."); valid_trade = False
                if tp_enabled and tp_price <= price: st.error("Take-Profit must be above current price."); valid_trade = False
                
                if valid_trade:
                    cost = price * shares_input
                    if st.session_state.cash_balance >= cost:
                        st.session_state.cash_balance -= cost
                        if st.session_state.main_ticker in st.session_state.portfolio:
                            current_shares = st.session_state.portfolio[st.session_state.main_ticker]['shares']
                            current_cost = st.session_state.portfolio[st.session_state.main_ticker]['avg_price'] * current_shares
                            total_shares = current_shares + shares_input
                            total_cost = current_cost + cost
                            st.session_state.portfolio[st.session_state.main_ticker]['avg_price'] = total_cost / total_shares
                            st.session_state.portfolio[st.session_state.main_ticker]['shares'] = total_shares
                        else: st.session_state.portfolio[st.session_state.main_ticker] = {'shares': shares_input, 'avg_price': price}
                        st.session_state.portfolio[st.session_state.main_ticker]['stop_loss'] = sl_price
                        st.session_state.portfolio[st.session_state.main_ticker]['take_profit'] = tp_price
                        st.session_state.trade_history.append({'timestamp': datetime.now().isoformat(), 'type': 'BUY', 'ticker': st.session_state.main_ticker, 'shares': shares_input, 'price': price, 'profit_loss': 0})
                        st.success(f"Bought {shares_input} of {st.session_state.main_ticker}!")
                        st.rerun()
                    else: st.error("Not enough cash.")

        if sell_col.button("Submit Sell Order", use_container_width=True):
            if not is_market_open(): st.error("Market is closed.")
            elif st.session_state.main_ticker not in st.session_state.portfolio or st.session_state.portfolio[st.session_state.main_ticker]['shares'] < shares_input: st.error("Not enough shares to sell.")
            else:
                price = get_current_price(st.session_state.main_ticker)
                if price:
                    proceeds = price * shares_input
                    st.session_state.cash_balance += proceeds
                    avg_price = st.session_state.portfolio[st.session_state.main_ticker]['avg_price']
                    profit_loss = (price - avg_price) * shares_input
                    st.session_state.portfolio[st.session_state.main_ticker]['shares'] -= shares_input
                    if st.session_state.portfolio[st.session_state.main_ticker]['shares'] == 0: del st.session_state.portfolio[st.session_state.main_ticker]
                    st.session_state.trade_history.append({'timestamp': datetime.now().isoformat(), 'type': 'SELL', 'ticker': st.session_state.main_ticker, 'shares': shares_input, 'price': price, 'profit_loss': profit_loss})
                    st.success(f"Sold {shares_input} of {st.session_state.main_ticker}!")
                    st.rerun()

    with st.expander("⭐ Watchlist"):
        watchlist_add = st.text_input("Add Ticker", key="watchlist_add").upper()
        if st.button("Add to Watchlist"):
            if watchlist_add and watchlist_add not in st.session_state.watchlist: st.session_state.watchlist.append(watchlist_add); st.rerun()
        st.dataframe(pd.DataFrame(st.session_state.watchlist, columns=["Ticker"]))

# This must be called before the main display elements
check_orders()

# --- COLUMN 2: Visual Display ---
with col2:
    st.header("📊 Market Visuals")
    
    with st.container(border=True):
        st.subheader(f"Interactive Chart for {st.session_state.main_ticker}")
        
        c_period = st.selectbox("Period", ["1d", "5d", "1mo", "6mo", "1y", "2y", "5y", "max"], index=2)
        c_interval = st.selectbox("Interval", ["1m", "2m", "5m", "15m", "30m", "1h", "1d", "1wk"], index=6)

        st.write("Moving Averages:")
        ma_col1, ma_col2, ma_col3, ma_col4, ma_col5 = st.columns(5)
        show_ema20 = ma_col1.checkbox("EMA (20)", value=True)
        show_sma10 = ma_col2.checkbox("SMA (10)")
        show_sma20 = ma_col3.checkbox("SMA (20)")
        show_sma50 = ma_col4.checkbox("SMA (50)")
        show_ema200 = ma_col5.checkbox("EMA (200)")

        auto_refresh = st.checkbox("Enable Auto-Refresh (every 30s)")
        
        chart_placeholder = st.empty()
        
        def draw_interactive_chart():
            try:
                history = yf.Ticker(st.session_state.main_ticker).history(period=c_period, interval=c_interval)
                if history.empty:
                    chart_placeholder.warning("No data found for the selected period/interval.")
                    return

                if show_ema20: history['EMA_20'] = ta.ema(history['Close'], length=20)
                if show_sma10: history['SMA_10'] = ta.sma(history['Close'], length=10)
                if show_sma20: history['SMA_20'] = ta.sma(history['Close'], length=20)
                if show_sma50: history['SMA_50'] = ta.sma(history['Close'], length=50)
                if show_ema200: history['EMA_200'] = ta.ema(history['Close'], length=200)

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=history.index, open=history['Open'], high=history['High'], low=history['Low'], close=history['Close'], name='Candlestick'), row=1, col=1)
                if show_ema20: fig.add_trace(go.Scatter(x=history.index, y=history['EMA_20'], mode='lines', name='EMA 20', line=dict(color='orange', width=1)), row=1, col=1)
                if show_sma10: fig.add_trace(go.Scatter(x=history.index, y=history['SMA_10'], mode='lines', name='SMA 10', line=dict(color='blue', width=1)), row=1, col=1)
                if show_sma20: fig.add_trace(go.Scatter(x=history.index, y=history['SMA_20'], mode='lines', name='SMA 20', line=dict(color='red', width=1)), row=1, col=1)
                if show_sma50: fig.add_trace(go.Scatter(x=history.index, y=history['SMA_50'], mode='lines', name='SMA 50', line=dict(color='green', width=1)), row=1, col=1)
                if show_ema200: fig.add_trace(go.Scatter(x=history.index, y=history['EMA_200'], mode='lines', name='EMA 200', line=dict(color='purple', width=1.5)), row=1, col=1)
                fig.add_trace(go.Bar(x=history.index, y=history['Volume'], name='Volume', marker_color='purple'), row=2, col=1)
                fig.update_layout(title=f'{st.session_state.main_ticker} Interactive Chart', xaxis_rangeslider_visible=False, xaxis_title="Date", yaxis_title="Price", height=600, hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                fig.update_yaxes(title_text="Price ($)", row=1, col=1)
                fig.update_yaxes(title_text="Volume", row=2, col=1)
                chart_placeholder.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                chart_placeholder.error(f"Could not load interactive chart: {e}")
        
        draw_interactive_chart()

    # --- TABS FOR ALL OTHER FEATURES ---
    portfolio_tab, history_tab, stats_tab, analysis_tab, news_tab, practice_tab, learn_tab = st.tabs(["💼 Portfolio", "📜 History", "🔍 Stats", "🔬 Analysis", "📰 News", "🎓 Practice", "📚 Learn"])
    
    with portfolio_tab:
        st.subheader("Your Holdings")
        if not st.session_state.portfolio: st.info("Your portfolio is empty.")
        else:
            items = []; total_value = 0
            for ticker, data in st.session_state.portfolio.items():
                price = get_current_price(ticker) or data['avg_price']; market_value = price * data['shares']; total_value += market_value
                items.append({"Ticker": ticker, "Shares": data['shares'], "Avg Price": f"${data['avg_price']:,.2f}", "Current Price": f"${price:,.2f}", "Market Value": f"${market_value:,.2f}", "Stop-Loss": f"${data.get('stop_loss'):,.2f}" if data.get('stop_loss') else "N/A", "Take-Profit": f"${data.get('take_profit'):,.2f}" if data.get('take_profit') else "N/A"})
            st.metric("Total Holdings Value", f"${total_value:,.2f}")
            st.dataframe(pd.DataFrame(items).set_index("Ticker"), use_container_width=True)

    with history_tab:
        st.subheader("Your Trade History")
        if not st.session_state.trade_history: st.info("No trades recorded yet.")
        else:
            history_df = pd.DataFrame(st.session_state.trade_history)
            history_df['timestamp'] = pd.to_datetime(history_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            st.dataframe(history_df[['timestamp', 'type', 'ticker', 'shares', 'price', 'profit_loss']].sort_index(ascending=False), use_container_width=True)

    with stats_tab:
        st.subheader("Daily Stock Stats"); s_ticker = st.session_state.main_ticker
        st.write(f"Showing stats for **{s_ticker}**.")
        try:
            info = yf.Ticker(s_ticker).info
            price = info.get('regularMarketPrice'); prev_close = info.get('previousClose'); change = price - prev_close; percent_change = (change / prev_close) * 100
            st.metric("Current Price", f"${price:,.2f}", f"{percent_change:,.2f}%"); st.text(f"Day's Range: ${info.get('dayLow'):,.2f} - ${info.get('dayHigh'):,.2f}"); st.text(f"Volume: {info.get('volume'):,}")
        except Exception: st.error("Could not retrieve stats for this ticker.")

    with analysis_tab:
        st.subheader("Analyze a Completed Trade")
        sell_trades = [t for t in st.session_state.trade_history if t['type'] == 'SELL']
        if not sell_trades: st.info("You must complete a trade to perform an analysis.")
        else:
            trade_options = [f"{t['ticker']} ({t['shares']} shares on {datetime.fromisoformat(t['timestamp']).strftime('%Y-%m-%d')})" for t in sell_trades]
            selected_trade_str = st.selectbox("Select a sell trade to analyze:", trade_options)
            if st.button("Analyze Trade"):
                selected_sell = sell_trades[trade_options.index(selected_trade_str)]; ticker = selected_sell['ticker']
                buy_trade = None
                for trade in reversed(st.session_state.trade_history):
                    if trade['type'] == 'BUY' and trade['ticker'] == ticker and datetime.fromisoformat(trade['timestamp']) < datetime.fromisoformat(selected_sell['timestamp']): buy_trade = trade; break
                if not buy_trade: st.error("Could not find a matching buy trade for this sale.")
                else:
                    buy_date = datetime.fromisoformat(buy_trade['timestamp']); sell_date = datetime.fromisoformat(selected_sell['timestamp'])
                    start_date = buy_date - timedelta(days=365); end_date = sell_date + timedelta(days=1)
                    with st.spinner("Fetching data and running analysis..."):
                        hist_data = yf.Ticker(ticker).history(start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
                        hist_data.ta.rsi(append=True); hist_data.ta.sma(length=50, append=True)
                        buy_day_data = hist_data.loc[buy_date.strftime('%Y-%m-%d')]; buy_rsi = buy_day_data['RSI_14'].iloc[0]
                        st.write(f"**Analysis for {ticker} Trade:**")
                        if buy_rsi < 35: st.success(f"✅ GOOD ENTRY: RSI was {buy_rsi:.2f} (possibly oversold).")
                        elif buy_rsi > 65: st.warning(f"❌ POOR ENTRY: RSI was {buy_rsi:.2f} (possibly overbought).")
                        else: st.info(f"UTRAL ENTRY: RSI was {buy_rsi:.2f} (neutral).")
                        holding_data = hist_data.loc[buy_date.strftime('%Y-%m-%d'):sell_date.strftime('%Y-%m-%d')]
                        highest_price = holding_data['High'].max(); potential_profit = (highest_price - buy_trade['price']) * selected_sell['shares']
                        st.write(f"Your actual P/L on this trade: **${selected_sell['profit_loss']:,.2f}**"); st.write(f"💡 POTENTIAL: Max profit could have been **${potential_profit:,.2f}**.")

    with news_tab:
        st.subheader(f"Latest News for {st.session_state.main_ticker}")
        try:
            news = yf.Ticker(st.session_state.main_ticker).news
            if not news: st.info("No recent news found for this ticker.")
            else:
                for item in news:
                    title = item.get('title'); link = item.get('link'); publisher = item.get('publisher'); publish_time = item.get('providerPublishTime')
                    if title and link:
                        st.write(f"**[{title}]({link})**")
                        if publisher and publish_time: st.caption(f"{publisher} - {datetime.fromtimestamp(publish_time).strftime('%Y-%m-%d %H:%M')}")
                        st.divider()
        except Exception as e: st.error(f"Could not fetch news: {e}")

    with practice_tab:
        st.subheader("Historical Trading Practice")
        if 'practice_data' not in st.session_state:
            with st.form("practice_setup"):
                st.write("Set up a practice session to trade on historical data.")
                practice_ticker = st.text_input("Ticker to practice with", "SPY").upper()
                start_date = st.date_input("Start Date for Data", datetime(2022, 1, 1))
                submitted = st.form_submit_button("Start Practice Session")
                if submitted:
                    with st.spinner("Downloading historical data..."):
                        end_date = datetime.now()
                        data = yf.Ticker(practice_ticker).history(start=start_date, end=end_date, interval="1d")
                        if not data.empty:
                            st.session_state.practice_data = data
                            st.session_state.practice_ticker = practice_ticker
                            st.session_state.practice_step = 50
                            st.session_state.practice_cash = 100000.0
                            st.session_state.practice_portfolio = {}
                            st.session_state.practice_trade_history = []
                            st.rerun()
                        else: st.error("Could not fetch data for this ticker/date range.")
        else:
            current_step = st.session_state.practice_step
            visible_data = st.session_state.practice_data.iloc[:current_step+1]
            current_date = visible_data.index[-1].strftime('%Y-%m-%d')
            current_price = visible_data['Close'].iloc[-1]
            st.write(f"Simulating Day: **{current_date}** | Current Price: **${current_price:,.2f}**")
            practice_chart = st.empty()
            fig = go.Figure(data=[go.Candlestick(x=visible_data.index, open=visible_data['Open'], high=visible_data['High'], low=visible_data['Low'], close=visible_data['Close'])])
            fig.update_layout(title=f"Practice Chart for {st.session_state.practice_ticker}", xaxis_rangeslider_visible=False)
            practice_chart.plotly_chart(fig, use_container_width=True)
            p_col1, p_col2 = st.columns(2)
            with p_col1: st.metric("Practice Cash", f"${st.session_state.practice_cash:,.2f}")
            with p_col2:
                if st.session_state.practice_portfolio:
                    st.write("Practice Holdings:"); st.json(st.session_state.practice_portfolio)
            ctl_col1, ctl_col2, ctl_col3, ctl_col4 = st.columns(4)
            practice_shares = ctl_col1.number_input("Shares", min_value=1, step=1, key="practice_shares")
            if ctl_col2.button("Buy (Practice)"):
                cost = current_price * practice_shares
                if st.session_state.practice_cash >= cost:
                    st.session_state.practice_cash -= cost
                    st.success(f"Bought {practice_shares} of {st.session_state.practice_ticker} in practice mode.")
                else: st.warning("Not enough practice cash.")
            if ctl_col3.button("Sell (Practice)"):
                st.success(f"Sold {practice_shares} of {st.session_state.practice_ticker} in practice mode.")
            if ctl_col4.button("Next Day >>"):
                if st.session_state.practice_step < len(st.session_state.practice_data) - 1:
                    st.session_state.practice_step += 1; st.rerun()
                else: st.success("You have reached the end of the historical data!")
            if st.button("End Practice Session"):
                del st.session_state.practice_data; st.rerun()
            st.subheader("Practice Trade History")
            if 'practice_trade_history' in st.session_state and st.session_state.practice_trade_history:
                practice_hist_df = pd.DataFrame(st.session_state.practice_trade_history)
                st.dataframe(practice_hist_df, use_container_width=True)
            else:
                st.info("No practice trades yet.")

    with learn_tab:
        st.subheader("📚 Day Trading Education")
        st.write("Here are some recommended videos from TJR's YouTube channel to help you learn the basics:")
        vid_col1, vid_col2 = st.columns(2)
        with vid_col1:
            st.video("https://www.youtube.com/watch?v=xgaep2fI6-Q")
        with vid_col2:
            st.video("https://www.youtube.com/watch?v=YGv6St0gy_I")
        st.divider()

        st.subheader("🧠 Test Your Knowledge")
        QUIZ_BANK = [
            {"question": "What does a green candlestick typically represent?", "options": ["The price went down", "The price went up", "The price stayed the same", "The market is closed"], "answer": "The price went up"},
            {"question": "What is the primary purpose of a 'Stop-Loss' order?", "options": ["To guarantee a profit", "To enter a trade at a specific price", "To limit potential losses on a trade", "To buy more shares automatically"], "answer": "To limit potential losses on a trade"},
            {"question": "The 'EMA (200)' on a chart is most often used to identify what?", "options": ["Short-term momentum", "The day's trading volume", "The long-term trend", "Immediate price reversals"], "answer": "The long-term trend"},
            {"question": "High trading 'Volume' during a price increase is often a sign of what?", "options": ["A weak trend", "A strong trend", "An impending price drop", "Low interest in the stock"], "answer": "A strong trend"},
            {"question": "What does 'RSI' stand for?", "options": ["Real-time Stock Index", "Relative Strength Index", "Return on Stock Investment", "Resistant Stock Indicator"], "answer": "Relative Strength Index"},
            {"question": "An RSI value above 70 often suggests a stock is...", "options": ["Oversold", "Fairly valued", "Overbought", "About to split"], "answer": "Overbought"},
            {"question": "A 'Take-Profit' order is used to...", "options": ["Automatically sell a stock to lock in profits at a target price", "Buy a stock when it hits a low price", "Cancel another order", "Calculate your total profit"], "answer": "Automatically sell a stock to lock in profits at a target price"},
            {"question": "The 'spread' in trading is the difference between...", "options": ["The high and low price of the day", "The bid and ask price", "The opening and closing price", "Your entry and exit price"], "answer": "The bid and ask price"}
        ]
        
        if 'current_quiz_questions' not in st.session_state:
            st.session_state.current_quiz_questions = random.sample(QUIZ_BANK, 3)

        if 'quiz_submitted' not in st.session_state:
            st.session_state.quiz_submitted = False
            
        if not st.session_state.quiz_submitted:
            with st.form("quiz_form"):
                user_answers = {}
                for i, q in enumerate(st.session_state.current_quiz_questions):
                    user_answers[i] = st.radio(q["question"], q["options"], key=f"q{i}")
                
                submitted = st.form_submit_button("Submit Quiz")
                if submitted:
                    st.session_state.user_answers = user_answers
                    st.session_state.quiz_submitted = True
                    st.rerun()
        else:
            score = 0
            for i, q in enumerate(st.session_state.current_quiz_questions):
                if st.session_state.user_answers[i] == q["answer"]:
                    score += 1
            
            total_questions = len(st.session_state.current_quiz_questions)
            score_percent = (score / total_questions) * 100
            
            st.write(f"### Your Score: {score}/{total_questions} ({score_percent:.0f}%)")
            if score_percent == 100: st.success("Excellent! You got all the answers right! 🎉")
            elif score_percent >= 60: st.warning("Good job! Review the incorrect answers to improve.")
            else: st.error("Keep studying! Review the videos and try again.")
            
            for i, q in enumerate(st.session_state.current_quiz_questions):
                if st.session_state.user_answers[i] != q["answer"]:
                    st.write(f"**Question:** {q['question']}")
                    st.write(f"**Your answer:** {st.session_state.user_answers[i]} (Incorrect)")
                    st.write(f"**Correct answer:** {q['answer']}")
                    st.divider()

            if st.button("Start New Quiz"):
                st.session_state.current_quiz_questions = random.sample(QUIZ_BANK, 3)
                st.session_state.quiz_submitted = False
                st.rerun()

if auto_refresh:
    time.sleep(30)
    st.rerun()