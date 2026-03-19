# streamlit_app.py
"""
ETH Monitor - 机构级 AI 量化交易系统
主应用入口
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import numpy as np

from config import DEFAULT_TRADE_SIZE, DEFAULT_TRADE_THRESHOLD, SIGNAL_THRESHOLD_STRONG
from trading_engine import engine
from ai_audit import auditor
from indicators import get_historical_prices, get_current_price, get_support_resistance, market_data
from okx_client import OKXClient, MockOKXClient

# 页面配置
st.set_page_config(
    page_title="ETH Monitor - 机构级AI量化系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 初始化 Session State ====================
def init_session_state():
    """初始化会话状态"""
    if 'account_balance' not in st.session_state:
        st.session_state.account_balance = 10000.0
    if 'auto_trade' not in st.session_state:
        st.session_state.auto_trade = False
    if 'last_trade_time' not in st.session_state:
        st.session_state.last_trade_time = None
    if 'client' not in st.session_state:
        st.session_state.client = None
    if 'trade_history' not in st.session_state:
        st.session_state.trade_history = []
    if 'last_plan' not in st.session_state:
        st.session_state.last_plan = None

init_session_state()

# ==================== 侧边栏配置 ====================
with st.sidebar:
    st.header("⚙️ 系统配置")
    
    # OKX API 配置
    st.subheader("🔐 OKX API")
    col_api1, col_api2 = st.columns(2)
    with col_api1:
        api_key = st.text_input("API Key", type="password", key="api_key_input")
        api_secret = st.text_input("API Secret", type="password", key="api_secret_input")
    with col_api2:
        passphrase = st.text_input("Passphrase", type="password", key="passphrase_input")
        simulate_mode = st.checkbox("模拟盘", value=True)
    
    # 连接按钮
    if st.button("连接 OKX", use_container_width=True):
        if api_key and api_secret and passphrase:
            client = OKXClient(api_key, api_secret, passphrase, simulate=simulate_mode)
            if client.test_connection():
                st.session_state.client = client
                acc = client.get_account()
                if acc.get('code') == '0' and acc.get('data'):
                    st.session_state.account_balance = float(acc['data'][0].get('totalEq', 10000))
                st.success(f"✅ 连接成功！余额: {st.session_state.account_balance:,.2f} USDT")
            else:
                st.error("❌ 连接失败，请检查API配置")
        else:
            st.session_state.client = MockOKXClient()
            st.info("📌 使用模拟模式")
    
    st.divider()
    
    # 自动交易设置
    st.subheader("🤖 自动交易")
    auto_trade = st.toggle("启用自动交易", value=st.session_state.auto_trade)
    if auto_trade != st.session_state.auto_trade:
        st.session_state.auto_trade = auto_trade
    
    if st.session_state.auto_trade:
        st.warning("⚠️ 自动交易已启用，系统将根据信号自动执行")
    
    trade_size = st.number_input("下单数量（张）", min_value=0.1, value=DEFAULT_TRADE_SIZE, step=0.1)
    trade_threshold = st.slider("交易阈值（信号强度%）", 0, 100, DEFAULT_TRADE_THRESHOLD, 5)
    
    st.divider()
    
    # 刷新设置
    st.subheader("🔄 刷新设置")
    auto_refresh = st.checkbox("自动刷新", value=True)
    refresh_rate = st.slider("刷新间隔（秒）", 5, 60, 10, 5) if auto_refresh else 60
    
    # 手动刷新按钮
    if st.button("🔄 立即刷新", use_container_width=True):
        market_data.refresh(force=True)
        st.rerun()
    
    st.divider()
    
    # 显示账户信息
    st.subheader("💰 账户信息")
    st.metric("账户余额", f"${st.session_state.account_balance:,.2f}")
    st.metric("连接状态", "已连接" if st.session_state.client else "未连接")

# ==================== 主界面 ====================
st.title("📊 ETH Monitor - 机构级 AI 量化交易系统")
st.caption(f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 刷新间隔: {refresh_rate}秒")

# ==================== 获取交易计划 ====================
plan = engine.generate_trading_plan(st.session_state.account_balance)
st.session_state.last_plan = plan

# ==================== K线图和信号面板 ====================
col_chart, col_signal = st.columns([3, 2])

with col_chart:
    st.subheader("📈 ETH/USDT 永续合约")
    
    # 获取历史数据
    dates, prices = get_historical_prices(60)
    
    # 创建K线图
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3]
    )
    
    # K线
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=[p * (1 + np.random.uniform(-0.01, 0.01)) for p in prices],
            high=[p * 1.02 for p in prices],
            low=[p * 0.98 for p in prices],
            close=prices,
            name="ETH"
        ),
        row=1, col=1
    )
    
    # 添加支撑压力位
    current_support = plan['support']
    current_resistance = plan['resistance']
    
    fig.add_hline(y=current_support, line_dash="dash", line_color="green", 
                  annotation_text=f"支撑 ${current_support:,.0f}", row=1, col=1)
    fig.add_hline(y=current_resistance, line_dash="dash", line_color="red",
                  annotation_text=f"压力 ${current_resistance:,.0f}", row=1, col=1)
    
    # 如果有交易计划，标记入场点
    if plan.get('tradeable'):
        fig.add_hline(y=plan['entry'], line_dash="dot", line_color="blue",
                      annotation_text=f"入场 ${plan['entry']:,.0f}", row=1, col=1)
    
    # 成交量
    volumes = [np.random.uniform(1000, 5000) for _ in prices]
    fig.add_trace(
        go.Bar(x=dates, y=volumes, name="成交量", marker_color='lightblue'),
        row=2, col=1
    )
    
    fig.update_layout(
        height=500,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=0, b=0)
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col_signal:
    # 实时指标卡片
    st.subheader("📊 市场概览")
    
    current_price = plan['current_price']
    support = plan['support']
    resistance = plan['resistance']
    
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("当前价格", f"${current_price:,.2f}")
    with col_m2:
        st.metric("支撑位", f"${support:,.2f}")
    with col_m3:
        st.metric("压力位", f"${resistance:,.2f}")
    
    st.divider()
    
    # 信号展示
    st.subheader("🎯 交易信号")
    
    direction = plan['direction']
    signal_quality = plan.get('signal_quality', '无')
    
    if direction == 'long':
        st.success(f"🟢 **做多信号**")
    elif direction == 'short':
        st.error(f"🔴 **做空信号**")
    else:
        st.info(f"⚪ **观望**")
    
    # 评分展示
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.metric("综合评分", f"{plan['composite_score']:.1f}")
    with col_s2:
        st.metric("信号强度", f"{plan['signal_strength']*100:.0f}%")
    with col_s3:
        st.metric("信号质量", signal_quality)
    
    # 冲突警告
    if plan.get('has_conflict'):
        st.warning(f"⚠️ {plan.get('conflict_desc', '检测到信号冲突')}")
    
    st.divider()
    
    # 不可交易原因
    if not plan.get('tradeable'):
        st.info(f"📋 {plan.get('reason', '无交易计划')}")

# ==================== 指标贡献分析 ====================
st.divider()
st.subheader("🔍 指标贡献分析")

scores = plan['scores']

# 指标详情展开
with st.expander("📊 查看各指标详情", expanded=True):
    col_i1, col_i2, col_i3 = st.columns(3)
    
    with col_i1:
        st.metric("量价口诀", f"{scores['volume_price']:.1f}", 
                  delta="多头" if scores['volume_price'] > 0 else "空头" if scores['volume_price'] < 0 else "中性")
        st.metric("多空共振", f"{scores['multi_resonance']:.1f}",
                  delta="多头" if scores['multi_resonance'] > 0 else "空头" if scores['multi_resonance'] < 0 else "中性")
    
    with col_i2:
        st.metric("市场结构", f"{scores['market_structure']:.1f}",
                  delta="多头" if scores['market_structure'] > 0 else "空头" if scores['market_structure'] < 0 else "中性")
        st.metric("LSTM预测", f"{scores['lstm_prediction']:.1f}",
                  delta="多头" if scores['lstm_prediction'] > 0 else "空头" if scores['lstm_prediction'] < 0 else "中性")
    
    with col_i3:
        st.metric("资金流向", f"{scores['money_flow']:.1f}",
                  delta="多头" if scores['money_flow'] > 0 else "空头" if scores['money_flow'] < 0 else "中性")
        st.metric("AI评分", f"{scores['ai_score']:.1f}",
                  delta="多头" if scores['ai_score'] > 0 else "空头" if scores['ai_score'] < 0 else "中性")

# 指标一致性分析
long_count = sum(1 for v in scores.values() if v > 10)
short_count = sum(1 for v in scores.values() if v < -10)
neutral_count = len(scores) - long_count - short_count

st.write(f"**指标一致性**: 🟢 {long_count} 多头 | 🔴 {short_count} 空头 | ⚪ {neutral_count} 中性")

# ==================== 交易计划 ====================
st.divider()
st.subheader("📋 交易计划")

if plan.get('tradeable'):
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    
    with col_p1:
        st.metric("入场价格", f"${plan['entry']:,.2f}")
    with col_p2:
        st.metric("止损价格", f"${plan['stop_loss']:,.2f}")
    with col_p3:
        st.metric("止盈价格", f"${plan['take_profit']:,.2f}")
    with col_p4:
        st.metric("建议仓位", f"${plan['position_size']:,.2f}")
    
    # 风险计算
    risk = abs(plan['entry'] - plan['stop_loss'])
    reward = abs(plan['take_profit'] - plan['entry'])
    rr_ratio = reward / risk if risk > 0 else 0
    
    st.write(f"**风险收益比**: 1:{rr_ratio:.1f} | **风险金额**: ${plan['position_size'] * risk / plan['entry']:.2f}")
    
    # 自动交易执行
    if st.session_state.auto_trade:
        if st.session_state.client is None:
            st.session_state.client = MockOKXClient()
        
        # 检查交易条件
        signal_pct = plan['signal_strength'] * 100
        
        if signal_pct >= trade_threshold and not plan.get('has_conflict'):
            # 频率控制
            now = time.time()
            if st.session_state.last_trade_time is None or (now - st.session_state.last_trade_time) > 60:
                
                if st.button("🚀 执行交易", type="primary", use_container_width=True):
                    side = 'buy' if direction == 'long' else 'sell'
                    posSide = 'long' if direction == 'long' else 'short'
                    
                    res = st.session_state.client.place_order(
                        instId='ETH-USDT-SWAP',
                        tdMode='cross',
                        side=side,
                        posSide=posSide,
                        sz=trade_size,
                        px=plan['entry']
                    )
                    
                    if res.get('code') == '0':
                        st.session_state.last_trade_time = now
                        st.session_state.trade_history.append({
                            'time': datetime.now(),
                            'direction': direction,
                            'price': plan['entry'],
                            'size': trade_size
                        })
                        st.rerun()
            else:
                wait_time = int(60 - (now - st.session_state.last_trade_time))
                st.caption(f"⏳ 冷却中，{wait_time}秒后可再次交易")
        else:
            st.caption(f"当前信号强度 {signal_pct:.0f}% 未达到阈值 {trade_threshold}%")
else:
    st.info(f"📌 {plan.get('reason', '暂无交易计划')}")

# ==================== AI 审计报告 ====================
st.divider()
st.subheader("🧠 AI 智能审计")

col_ai1, col_ai2 = st.columns([1, 2])

with col_ai1:
    if st.button("生成 AI 审计报告", type="secondary", use_container_width=True):
        with st.spinner("AI 正在分析..."):
            market_summary = plan.get('market_summary', {})
            ai_score, report = auditor.audit(market_summary, plan['scores'])
            st.session_state.ai_report = report
            st.session_state.ai_score = ai_score
            st.rerun()

with col_ai2:
    if 'ai_report' in st.session_state:
        st.markdown(st.session_state.ai_report)
    else:
        st.caption("点击左侧按钮生成 AI 分析报告")

# ==================== 交易历史 ====================
if st.session_state.trade_history:
    st.divider()
    st.subheader("📜 交易历史")
    
    history_df = pd.DataFrame(st.session_state.trade_history[-10:])
    if not history_df.empty:
        history_df['time'] = pd.to_datetime(history_df['time']).dt.strftime('%H:%M:%S')
        st.dataframe(history_df, use_container_width=True, hide_index=True)

# ==================== 页脚信息 ====================
st.divider()
st.caption(f"""
**ETH Monitor v2.0** | 机构级 AI 量化交易系统
- 多维度指标分析 | AI 智能审计 | 自动风险管理
- 刷新间隔: {refresh_rate}秒 | 自动刷新: {'✅' if auto_refresh else '❌'}
""")
