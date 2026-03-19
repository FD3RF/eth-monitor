# config.py
import os

# ================== AI 模型配置 ==================
AI_MODEL = os.getenv("AI_MODEL", "gemma3:1b")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", 30))
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", 3))

# 熔断机制
AI_FAIL_COOLDOWN = int(os.getenv("AI_FAIL_COOLDOWN", 60))
AI_MAX_FAIL_COUNT = int(os.getenv("AI_MAX_FAIL_COUNT", 5))

# ================== 交易配置 ==================
DEFAULT_TRADE_SIZE = float(os.getenv("DEFAULT_TRADE_SIZE", 1.0))
DEFAULT_TRADE_THRESHOLD = int(os.getenv("DEFAULT_TRADE_THRESHOLD", 70))

# ================== 风险控制 ==================
RISK_PER_TRADE = 0.02          # 每次交易风险 2%
MAX_POSITION_RATIO = 0.3       # 最大仓位占账户比例 30%
REWARD_RISK_RATIO = 2.0        # 风险收益比 1:2

# ================== 指标权重 ==================
WEIGHTS = {
    "volume_price": 0.25,       # 量价口诀
    "ai_score": 0.20,           # AI 快速评分
    "multi_resonance": 0.20,    # 多空共振
    "market_structure": 0.15,   # 市场结构
    "lstm_prediction": 0.10,    # LSTM 预测
    "money_flow": 0.10          # 资金流向
}

# ================== 信号阈值 ==================
SIGNAL_THRESHOLD_STRONG = 0.6    # 强信号阈值（归一化后）
SIGNAL_THRESHOLD_WEAK = 0.3      # 弱信号阈值
CONFLICT_THRESHOLD = 0.4         # 冲突检测阈值

# ================== 评分范围定义 ==================
SCORE_RANGES = {
    "volume_price": {"min": -100, "max": 100},
    "ai_score": {"min": -100, "max": 100},
    "multi_resonance": {"min": -100, "max": 100},
    "market_structure": {"min": -100, "max": 100},
    "lstm_prediction": {"min": -100, "max": 100},
    "money_flow": {"min": -100, "max": 100}
}
