"""
以太坊 5 分钟合约高频交易策略 - Streamlit 应用（最终完美版）

功能：
- 每 60 秒自动获取最新 200 根 5 分钟 K 线
- 计算 EMA12、EMA26、RSI14
- 金叉/死叉 + RSI 阈值生成信号（可调参数）
- 模拟持仓管理（止盈止损、EMA26反向、滑点模拟）
- 复合收益率统计、胜率、算术平均盈亏
- 交互式K线图（开仓三角形、平仓圆圈，颜色区分盈亏）
- 侧边栏实时调整策略参数

运行方式：
    pip install -r requirements.txt
    streamlit run app.py
"""

import time
import ccxt
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# ==================== 固定参数 ====================
SYMBOL = 'ETH/USDT'
TIMEFRAME = '5m'
LIMIT = 200
REFRESH_INTERVAL = 60          # 秒
MAX_SIGNAL_HISTORY = 1000      # 最多保留信号条数
MIN_VALID_BARS = 26            # 指标稳定所需最少K线数

# ==================== Session 状态初始化 ====================
def init_session_state():
    """初始化所有 session state 变量"""
    if 'position_state' not in st.session_state:
        st.session_state.position_state = {
            'position': 'none',
            'entry_price': None,
            'stop_loss': None,
            'take_profit': None,
            'last_processed_ts': None,
        }
    if 'signals_history' not in st.session_state:
        st.session_state.signals_history = []
    # 复合收益率（小数，例如 0.05 表示 5%）
    if 'total_pnl_compound' not in st.session_state:
        st.session_state.total_pnl_compound = 0.0
    # 算术累加盈亏（用于计算平均盈亏）
    if 'total_pnl_arithmetic' not in st.session_state:
        st.session_state.total_pnl_arithmetic = 0.0
    if 'total_trades' not in st.session_state:
        st.session_state.total_trades = 0
    if 'winning_trades' not in st.session_state:
        st.session_state.winning_trades = 0
    if 'last_open_signal_type' not in st.session_state:
        st.session_state.last_open_signal_type = None   # 用于信号去重


# ==================== 数据获取 ====================
def fetch_ohlcv(retries=3, delay=2):
    """从 Binance 获取最新 K 线，带重试"""
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    for attempt in range(retries):
        try:
            ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=LIMIT)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            # 去除重复时间戳（如果存在）
            df = df[~df.index.duplicated(keep='first')]
            return df
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                st.error(f"数据获取失败: {e}")
                return pd.DataFrame()
    return pd.DataFrame()


# ==================== 指标计算 ====================
def add_indicators(df):
    """添加 EMA12, EMA26, RSI14，丢弃前 MIN_VALID_BARS 根不稳定K线"""
    if len(df) < MIN_VALID_BARS:
        st.warning(f"数据不足 {MIN_VALID_BARS} 根，当前仅 {len(df)} 根，等待积累...")
        return pd.DataFrame()
    df = df.copy()
    df['EMA12'] = ta.ema(df['close'], length=12)
    df['EMA26'] = ta.ema(df['close'], length=26)
    df['RSI'] = ta.rsi(df['close'], length=14)
    # 丢弃前 MIN_VALID_BARS 根（指标尚未稳定）
    df = df.iloc[MIN_VALID_BARS:].copy()
    return df


# ==================== 策略逻辑 ====================
def detect_signals(df, rsi_long_threshold, rsi_short_threshold):
    """生成信号：1=做多，-1=做空，0=无信号"""
    df = df.copy()
    df['ema12_above'] = df['EMA12'] > df['EMA26']
    df['golden_cross'] = (df['ema12_above'] == True) & (df['ema12_above'].shift(1) == False)
    df['death_cross'] = (df['ema12_above'] == False) & (df['ema12_above'].shift(1) == True)

    df['signal'] = 0
    # 互斥赋值，避免浮点误差同时满足
    df.loc[df['golden_cross'] & (df['RSI'] > rsi_long_threshold), 'signal'] = 1
    df.loc[(df['signal'] == 0) & df['death_cross'] & (df['RSI'] < rsi_short_threshold), 'signal'] = -1
    return df


# ==================== 模拟交易 ====================
def simulate_trading(df, position_state, stop_loss_pct, take_profit_pct, slippage_pct):
    """
    模拟持仓管理，返回新状态、新信号、平仓盈亏
    滑点：做多开仓+滑点，平仓-滑点；做空开仓-滑点，平仓+滑点
    """
    state = position_state.copy()
    new_signals = []
    pnl_record = None  # 本次平仓盈亏（百分比）

    if 'signal' not in df.columns or len(df) == 0:
        return state, new_signals, pnl_record

    # 定位新K线起始索引
    last_ts = state.get('last_processed_ts')
    if last_ts is None:
        start_idx = 0
    else:
        mask = df.index > last_ts
        if not mask.any():
            return state, new_signals, pnl_record
        start_idx = mask.idxmax()
        start_idx = df.index.get_loc(start_idx)

    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        current_time = row.name
        slippage = slippage_pct / 100

        # ----- 平仓检查 -----
        close_signal = False
        close_reason = None
        exit_price = None

        if state['position'] == 'long':
            exit_price = row['close'] * (1 - slippage)          # 做多平仓价格（卖价）
            if exit_price <= state['stop_loss'] or exit_price >= state['take_profit']:
                close_signal = True
                close_reason = '止盈止损'
            elif exit_price < row['EMA26']:
                close_signal = True
                close_reason = '跌破 EMA26'
            elif row['signal'] == -1:
                close_signal = True
                close_reason = '做空信号'

        elif state['position'] == 'short':
            exit_price = row['close'] * (1 + slippage)          # 做空平仓价格（买价）
            if exit_price >= state['stop_loss'] or exit_price <= state['take_profit']:
                close_signal = True
                close_reason = '止盈止损'
            elif exit_price > row['EMA26']:
                close_signal = True
                close_reason = '突破 EMA26'
            elif row['signal'] == 1:
                close_signal = True
                close_reason = '做多信号'

        if close_signal:
            # 计算盈亏百分比
            if state['position'] == 'long':
                pnl_pct = (exit_price - state['entry_price']) / state['entry_price'] * 100
            else:
                pnl_pct = (state['entry_price'] - exit_price) / state['entry_price'] * 100

            new_signals.append({
                'time': current_time,
                'type': f'平{state["position"]}',
                'price': exit_price,
                'reason': close_reason,
                'entry_price': state['entry_price'],
                'pnl_pct': pnl_pct,
                'is_win': pnl_pct > 0
            })
            pnl_record = pnl_pct

            state['position'] = 'none'
            state['entry_price'] = None
            state['stop_loss'] = None
            state['take_profit'] = None
            # 平仓后重置开仓信号类型，允许后续同向信号
            st.session_state.last_open_signal_type = None

        # ----- 开仓检查（无持仓时）-----
        if state['position'] == 'none':
            if row['signal'] == 1:
                entry_price = row['close'] * (1 + slippage)     # 做多开仓价格（买价）
                # 去重：若上一个开仓信号已经是做多，则跳过
                if st.session_state.last_open_signal_type == '做多':
                    continue
                state['position'] = 'long'
                state['entry_price'] = entry_price
                state['stop_loss'] = entry_price * (1 - stop_loss_pct)
                state['take_profit'] = entry_price * (1 + take_profit_pct)
                new_signals.append({
                    'time': current_time,
                    'type': '做多',
                    'price': entry_price,
                    'reason': f'金叉+RSI>{rsi_long_threshold}',
                    'entry_price': entry_price,
                    'pnl_pct': None,
                    'is_win': None
                })
                st.session_state.last_open_signal_type = '做多'
            elif row['signal'] == -1:
                entry_price = row['close'] * (1 - slippage)     # 做空开仓价格（卖价）
                if st.session_state.last_open_signal_type == '做空':
                    continue
                state['position'] = 'short'
                state['entry_price'] = entry_price
                state['stop_loss'] = entry_price * (1 + stop_loss_pct)
                state['take_profit'] = entry_price * (1 - take_profit_pct)
                new_signals.append({
                    'time': current_time,
                    'type': '做空',
                    'price': entry_price,
                    'reason': f'死叉+RSI<{rsi_short_threshold}',
                    'entry_price': entry_price,
                    'pnl_pct': None,
                    'is_win': None
                })
                st.session_state.last_open_signal_type = '做空'

    # 更新最后处理的时间戳
    if len(df) > 0:
        state['last_processed_ts'] = df.index[-1]

    return state, new_signals, pnl_record


# ==================== 统计更新 ====================
def update_statistics(pnl_record):
    """更新累计统计：复合收益率、算术累加盈亏、胜率"""
    if pnl_record is None:
        return
    st.session_state.total_trades += 1
    if pnl_record > 0:
        st.session_state.winning_trades += 1

    # 复合收益率（小数）
    old_compound = st.session_state.total_pnl_compound
    new_compound = (1 + old_compound) * (1 + pnl_record / 100) - 1
    st.session_state.total_pnl_compound = new_compound

    # 算术累加盈亏（用于平均盈亏）
    st.session_state.total_pnl_arithmetic += pnl_record


# ==================== 绘图 ====================
def plot_candlestick(df, signals):
    """绘制K线图，开仓用三角形，平仓用圆圈（盈利绿色/亏损红色）"""
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='K线'
    ))

    fig.add_trace(go.Scatter(
        x=df.index, y=df['EMA12'], mode='lines', name='EMA12',
        line=dict(color='orange', width=1)
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df['EMA26'], mode='lines', name='EMA26',
        line=dict(color='blue', width=1)
    ))

    # 开仓信号（三角形）
    for sig in signals:
        if sig['type'] in ['做多', '做空']:
            marker_color = 'green' if sig['type'] == '做多' else 'red'
            marker_symbol = 'triangle-up' if sig['type'] == '做多' else 'triangle-down'
            fig.add_trace(go.Scatter(
                x=[sig['time']],
                y=[sig['price']],
                mode='markers',
                marker=dict(symbol=marker_symbol, size=12, color=marker_color),
                name=sig['type'],
                text=f"{sig['type']} @ {sig['price']:.2f}",
                hoverinfo='text'
            ))
        elif sig['type'].startswith('平'):
            # 平仓信号（圆圈），颜色区分盈亏
            if sig['pnl_pct'] is not None:
                marker_color = 'lightgreen' if sig['pnl_pct'] > 0 else 'lightcoral'
            else:
                marker_color = 'gray'
            fig.add_trace(go.Scatter(
                x=[sig['time']],
                y=[sig['price']],
                mode='markers',
                marker=dict(symbol='circle', size=8, color=marker_color),
                name='平仓',
                text=f"{sig['type']} @ {sig['price']:.2f} 盈亏:{sig['pnl_pct']:.2f}%" if sig['pnl_pct'] is not None else f"{sig['type']} @ {sig['price']:.2f}",
                hoverinfo='text'
            ))

    fig.update_layout(
        title=f'{SYMBOL} 5分钟K线图',
        xaxis_title='时间',
        yaxis_title='价格',
        height=600,
        xaxis_rangeslider_visible=False,
        template='plotly_dark'
    )
    return fig


# ==================== 主程序 ====================
def main():
    st.set_page_config(page_title="ETH/USDT 5min 高频策略", layout="wide")
    st.title("ETH/USDT 5分钟合约高频策略监控")

    init_session_state()

    # ---------- 侧边栏参数 ----------
    st.sidebar.header("策略参数配置")
    stop_loss_pct = st.sidebar.slider("止损百分比 (%)", 0.5, 3.0, 1.5, 0.1) / 100
    take_profit_pct = st.sidebar.slider("止盈百分比 (%)", 1.0, 5.0, 2.0, 0.1) / 100
    rsi_long_threshold = st.sidebar.slider("做多 RSI 阈值 (需大于)", 50, 70, 55, 1)
    rsi_short_threshold = st.sidebar.slider("做空 RSI 阈值 (需小于)", 30, 50, 45, 1)
    slippage_pct = st.sidebar.slider("滑点模拟 (%)", 0.0, 0.2, 0.05, 0.01)

    st.sidebar.markdown("---")
    st.sidebar.write("**当前参数**")
    st.sidebar.write(f"止损: {stop_loss_pct*100:.1f}%")
    st.sidebar.write(f"止盈: {take_profit_pct*100:.1f}%")
    st.sidebar.write(f"做多 RSI 阈值: >{rsi_long_threshold}")
    st.sidebar.write(f"做空 RSI 阈值: <{rsi_short_threshold}")
    st.sidebar.write(f"滑点: {slippage_pct:.2f}%")

    # 自动刷新
    st_autorefresh(interval=REFRESH_INTERVAL * 1000, key="data_refresh")

    try:
        df_raw = fetch_ohlcv()
        if df_raw.empty:
            st.error("⚠️ 无法获取数据，请检查网络连接。")
            return

        df = add_indicators(df_raw)
        if df.empty:
            st.warning(f"数据不足 {MIN_VALID_BARS} 根，等待数据积累...")
            return

        df = detect_signals(df, rsi_long_threshold, rsi_short_threshold)

        new_state, new_signals, pnl_record = simulate_trading(
            df, st.session_state.position_state,
            stop_loss_pct, take_profit_pct, slippage_pct
        )
        st.session_state.position_state = new_state

        if pnl_record is not None:
            update_statistics(pnl_record)

        for sig in new_signals:
            st.session_state.signals_history.append(sig)
            if len(st.session_state.signals_history) > MAX_SIGNAL_HISTORY:
                st.session_state.signals_history = st.session_state.signals_history[-MAX_SIGNAL_HISTORY:]

    except Exception as e:
        st.error("策略运行出错，详情如下：")
        st.exception(e)
        return

    # ---------- 界面显示 ----------
    last_price = df['close'].iloc[-1]
    col1, col2, col3 = st.columns(3)
    col1.metric("最新价格", f"{last_price:.2f} USDT")
    col2.metric("当前持仓", st.session_state.position_state['position'].upper())
    # 复合收益率（百分比）
    col3.metric("累计收益率", f"{st.session_state.total_pnl_compound*100:.2f}%")

    if st.session_state.total_trades > 0:
        win_rate = st.session_state.winning_trades / st.session_state.total_trades * 100
        avg_win = st.session_state.total_pnl_arithmetic / st.session_state.total_trades
    else:
        win_rate = 0
        avg_win = 0
    col4, col5, col6 = st.columns(3)
    col4.metric("总交易次数", st.session_state.total_trades)
    col5.metric("胜率", f"{win_rate:.1f}%")
    col6.metric("平均盈亏", f"{avg_win:.2f}%")

    if new_signals:
        st.subheader("🎯 新信号")
        for sig in new_signals:
            if sig['type'] == '做多':
                st.success(f"🟢 {sig['type']} @ {sig['price']:.2f}  理由：{sig['reason']}")
            elif sig['type'] == '做空':
                st.error(f"🔴 {sig['type']} @ {sig['price']:.2f}  理由：{sig['reason']}")
            else:
                pnl_str = f"  盈亏：{sig['pnl_pct']:.2f}%" if sig['pnl_pct'] is not None else ""
                st.info(f"🔄 {sig['type']} @ {sig['price']:.2f}  理由：{sig['reason']}{pnl_str}")

    if st.session_state.signals_history:
        history_df = pd.DataFrame(st.session_state.signals_history[-20:])
        cols_to_show = ['time', 'type', 'price', 'reason']
        if 'pnl_pct' in history_df.columns:
            cols_to_show.append('pnl_pct')
        history_df = history_df[cols_to_show].copy()
        history_df['time'] = history_df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
        if 'price' in history_df.columns:
            history_df['price'] = history_df['price'].round(2)
        if 'pnl_pct' in history_df.columns:
            history_df['pnl_pct'] = history_df['pnl_pct'].round(2).fillna('')
        st.write("#### 最近信号记录")
        st.dataframe(history_df, use_container_width=True)

    st.write("#### K 线图与信号标记")
    signals_to_plot = [s for s in st.session_state.signals_history if s['time'] >= df.index[0]]
    fig = plot_candlestick(df, signals_to_plot)
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        f"数据更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"自动刷新间隔 {REFRESH_INTERVAL} 秒 | "
        f"已丢弃前 {MIN_VALID_BARS} 根不稳定K线"
    )
    if st.button("🔄 立即刷新"):
        st.experimental_rerun()


if __name__ == "__main__":
    main()
