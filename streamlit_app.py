"""
以太坊 5 分钟合约高频交易策略 - Streamlit 应用

功能：
- 每 60 秒自动获取最新 200 根 5 分钟 K 线
- 计算 EMA12、EMA26、RSI14
- 根据金叉/死叉 + RSI 条件生成做多/做空信号
- 模拟持仓管理（含止盈止损、EMA26 反向平仓）
- 交互式 K 线图（标记信号点，显示均线）
- 实时显示持仓状态、最新价格、信号历史

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
from datetime import datetime

# ==================== 配置参数 ====================
SYMBOL = 'ETH/USDT'
TIMEFRAME = '5m'
LIMIT = 200
REFRESH_INTERVAL = 60  # 秒
STOP_LOSS_PCT = 0.015  # 1.5%
TAKE_PROFIT_PCT = 0.02  # 2%

# ==================== 数据获取 ====================
@st.cache_data(ttl=REFRESH_INTERVAL)
def fetch_ohlcv():
    """
    从 Binance 获取最新 K 线数据
    使用缓存避免频繁请求，ttl 与刷新间隔一致
    """
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}  # 使用永续合约数据
    })
    try:
        ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=LIMIT)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        st.error(f"数据获取失败: {e}")
        # 返回空 DataFrame
        return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])


# ==================== 指标计算 ====================
def add_indicators(df):
    """添加 EMA12, EMA26, RSI14"""
    df = df.copy()
    df['EMA12'] = ta.ema(df['close'], length=12)
    df['EMA26'] = ta.ema(df['close'], length=26)
    df['RSI'] = ta.rsi(df['close'], length=14)
    return df


# ==================== 策略逻辑 ====================
def detect_signals(df):
    """
    基于金叉/死叉和 RSI 生成信号
    返回信号列：'signal' = 1 为做多，-1 为做空，0 为无信号
    """
    df = df.copy()
    df['ema12_above'] = df['EMA12'] > df['EMA26']
    df['golden_cross'] = (df['ema12_above'] == True) & (df['ema12_above'].shift(1) == False)
    df['death_cross'] = (df['ema12_above'] == False) & (df['ema12_above'].shift(1) == True)

    df['signal'] = 0
    df.loc[df['golden_cross'] & (df['RSI'] > 50), 'signal'] = 1
    df.loc[df['death_cross'] & (df['RSI'] < 50), 'signal'] = -1
    return df


def simulate_trading(df, position_state):
    """
    根据信号模拟持仓，返回新的持仓状态和新产生的信号记录
    position_state 包含：
        - position: 'long', 'short', 'none'
        - entry_price
        - stop_loss
        - take_profit
        - signals (历史信号列表)
    """
    state = position_state.copy()
    new_signals = []

    # 确保 df 已包含信号列
    if 'signal' not in df.columns:
        return state, new_signals

    # 只处理新出现的K线（从上次最后处理的时间戳之后）
    last_processed_ts = state.get('last_processed_ts', None)
    if last_processed_ts is None:
        # 首次运行，处理所有 K 线
        start_idx = 0
    else:
        # 找到最后一个已处理 K 线的位置
        start_idx = df.index.get_indexer([last_processed_ts], method='pad')[0]
        if start_idx < 0:
            start_idx = 0
        else:
            start_idx += 1

    if start_idx >= len(df):
        return state, new_signals

    for i in range(start_idx, len(df)):
        row = df.iloc[i]
        current_time = row.name
        current_price = row['close']

        # 平仓检查（优先于新开仓）
        close_signal = False
        close_reason = None

        if state['position'] == 'long':
            # 止盈止损
            if current_price <= state['stop_loss'] or current_price >= state['take_profit']:
                close_signal = True
                close_reason = '止盈止损'
            # 反向跌破 EMA26
            elif current_price < row['EMA26']:
                close_signal = True
                close_reason = '跌破 EMA26'
            # 出现做空信号
            elif row['signal'] == -1:
                close_signal = True
                close_reason = '做空信号'

        elif state['position'] == 'short':
            if current_price >= state['stop_loss'] or current_price <= state['take_profit']:
                close_signal = True
                close_reason = '止盈止损'
            elif current_price > row['EMA26']:
                close_signal = True
                close_reason = '突破 EMA26'
            elif row['signal'] == 1:
                close_signal = True
                close_reason = '做多信号'

        if close_signal:
            # 记录平仓信号
            new_signals.append({
                'time': current_time,
                'type': f'平{state["position"]}',
                'price': current_price,
                'reason': close_reason,
                'entry_price': state['entry_price']
            })
            state['position'] = 'none'
            state['entry_price'] = None
            state['stop_loss'] = None
            state['take_profit'] = None

        # 开仓检查（无持仓时）
        if state['position'] == 'none':
            if row['signal'] == 1:   # 做多
                state['position'] = 'long'
                state['entry_price'] = current_price
                state['stop_loss'] = current_price * (1 - STOP_LOSS_PCT)
                state['take_profit'] = current_price * (1 + TAKE_PROFIT_PCT)
                new_signals.append({
                    'time': current_time,
                    'type': '做多',
                    'price': current_price,
                    'reason': '金叉+RSI>50',
                    'entry_price': current_price
                })
            elif row['signal'] == -1:  # 做空
                state['position'] = 'short'
                state['entry_price'] = current_price
                state['stop_loss'] = current_price * (1 + STOP_LOSS_PCT)
                state['take_profit'] = current_price * (1 - TAKE_PROFIT_PCT)
                new_signals.append({
                    'time': current_time,
                    'type': '做空',
                    'price': current_price,
                    'reason': '死叉+RSI<50',
                    'entry_price': current_price
                })

    # 更新最后处理的时间戳
    if len(df) > 0:
        state['last_processed_ts'] = df.index[-1]

    return state, new_signals


# ==================== 绘图 ====================
def plot_candlestick(df, signals):
    """
    绘制 K 线图，并标注信号点，添加均线
    signals 为信号列表，每个元素包含 time, type, price
    """
    fig = go.Figure()

    # 添加 K 线
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='K线'
    ))

    # 添加 EMA12 和 EMA26
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA12'], mode='lines', name='EMA12', line=dict(color='orange', width=1)))
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA26'], mode='lines', name='EMA26', line=dict(color='blue', width=1)))

    # 添加信号标记
    for sig in signals:
        marker_color = 'green' if sig['type'] == '做多' else 'red'
        marker_symbol = 'triangle-up' if sig['type'] == '做多' else 'triangle-down'
        # 找到对应时间点的价格
        price = sig['price']
        fig.add_trace(go.Scatter(
            x=[sig['time']],
            y=[price],
            mode='markers',
            marker=dict(symbol=marker_symbol, size=12, color=marker_color),
            name=sig['type'],
            text=f"{sig['type']} @ {price:.2f}",
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

    # 初始化 session state
    if 'position_state' not in st.session_state:
        st.session_state.position_state = {
            'position': 'none',
            'entry_price': None,
            'stop_loss': None,
            'take_profit': None,
            'last_processed_ts': None,
        }
    if 'signals_history' not in st.session_state:
        st.session_state.signals_history = []  # 所有历史信号

    placeholder = st.empty()

    while True:
        with placeholder.container():
            st.write("### 实时数据与信号")
            # 获取数据
            df_raw = fetch_ohlcv()
            if df_raw.empty:
                st.error("无法获取数据，请检查网络后重试。")
                time.sleep(REFRESH_INTERVAL)
                continue

            # 计算指标
            df = add_indicators(df_raw)
            df = detect_signals(df)

            # 模拟交易
            new_state, new_signals = simulate_trading(df, st.session_state.position_state)
            st.session_state.position_state = new_state

            # 更新信号历史
            if new_signals:
                st.session_state.signals_history.extend(new_signals)

            # 显示最新价格和持仓状态
            last_price = df['close'].iloc[-1]
            col1, col2 = st.columns(2)
            col1.metric("最新价格", f"{last_price:.2f} USDT")
            col2.metric("当前持仓", st.session_state.position_state['position'].upper())

            # 信号提示区（新信号高亮）
            if new_signals:
                last_signal = new_signals[-1]
                if last_signal['type'] == '做多':
                    st.success(f"🎯 新信号：{last_signal['type']} @ {last_signal['price']:.2f}  理由：{last_signal['reason']}")
                else:
                    st.error(f"🎯 新信号：{last_signal['type']} @ {last_signal['price']:.2f}  理由：{last_signal['reason']}")

            # 历史信号表格（最近20条）
            if st.session_state.signals_history:
                history_df = pd.DataFrame(st.session_state.signals_history[-20:])
                history_df = history_df[['time', 'type', 'price', 'reason']].copy()
                history_df['time'] = history_df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
                history_df['price'] = history_df['price'].round(2)
                st.write("#### 最近信号记录")
                st.dataframe(history_df, use_container_width=True)

            # K 线图（仅显示最近 200 根，与数据一致）
            st.write("#### K 线图与信号标记")
            # 仅展示当前数据范围内的信号
            signals_to_plot = [s for s in st.session_state.signals_history if s['time'] >= df.index[0]]
            fig = plot_candlestick(df, signals_to_plot)
            st.plotly_chart(fig, use_container_width=True)

            # 底部状态栏
            st.caption(f"数据更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 每 {REFRESH_INTERVAL} 秒自动刷新")

        # 等待下一次刷新
        time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    main()
