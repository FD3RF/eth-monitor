#!/usr/bin/env python3
"""
模块测试脚本 - 验证所有模块能正常导入和运行
"""
import sys
import traceback

def test_imports():
    """测试所有模块导入"""
    print("=" * 50)
    print("📦 测试模块导入...")
    print("=" * 50)
    
    modules = [
        ("config", "配置模块"),
        ("indicators", "指标计算模块"),
        ("ai_audit", "AI审计模块"),
        ("risk_manager", "风险管理模块"),
        ("trading_engine", "交易引擎模块"),
        ("okx_client", "OKX客户端模块"),
    ]
    
    success_count = 0
    for module_name, description in modules:
        try:
            __import__(module_name)
            print(f"✅ {description} ({module_name})")
            success_count += 1
        except Exception as e:
            print(f"❌ {description} ({module_name}): {e}")
            traceback.print_exc()
    
    print(f"\n导入测试完成: {success_count}/{len(modules)} 成功")
    return success_count == len(modules)


def test_indicators():
    """测试指标计算"""
    print("\n" + "=" * 50)
    print("📊 测试指标计算...")
    print("=" * 50)
    
    try:
        from indicators import (
            get_current_price, get_support_resistance,
            calculate_volume_price, calculate_multi_resonance,
            calculate_market_structure, calculate_lstm_prediction,
            calculate_money_flow
        )
        
        price = get_current_price()
        print(f"当前价格: ${price:,.2f}")
        
        support, resistance = get_support_resistance()
        print(f"支撑位: ${support:,.2f} | 压力位: ${resistance:,.2f}")
        
        vp = calculate_volume_price()
        mr = calculate_multi_resonance()
        ms = calculate_market_structure()
        lstm = calculate_lstm_prediction()
        mf = calculate_money_flow()
        
        print(f"\n指标评分:")
        print(f"  量价口诀: {vp:>8.1f}")
        print(f"  多空共振: {mr:>8.1f}")
        print(f"  市场结构: {ms:>8.1f}")
        print(f"  LSTM预测: {lstm:>8.1f}")
        print(f"  资金流向: {mf:>8.1f}")
        
        print("\n✅ 指标计算测试通过")
        return True
    except Exception as e:
        print(f"❌ 指标计算测试失败: {e}")
        traceback.print_exc()
        return False


def test_trading_engine():
    """测试交易引擎"""
    print("\n" + "=" * 50)
    print("🎯 测试交易引擎...")
    print("=" * 50)
    
    try:
        from trading_engine import engine
        
        plan = engine.generate_trading_plan(account_balance=10000.0)
        
        print(f"方向: {plan['direction']}")
        print(f"综合评分: {plan['composite_score']:.1f}")
        print(f"信号强度: {plan['signal_strength']*100:.0f}%")
        print(f"信号质量: {plan.get('signal_quality', 'N/A')}")
        print(f"是否冲突: {'是' if plan.get('has_conflict') else '否'}")
        print(f"可交易: {'是' if plan.get('tradeable') else '否'}")
        
        if plan.get('tradeable'):
            print(f"\n交易计划:")
            print(f"  入场价: ${plan['entry']:,.2f}")
            print(f"  止损价: ${plan['stop_loss']:,.2f}")
            print(f"  止盈价: ${plan['take_profit']:,.2f}")
            print(f"  仓位: ${plan['position_size']:,.2f} USDT")
        else:
            print(f"\n原因: {plan.get('reason', 'N/A')}")
        
        print("\n✅ 交易引擎测试通过")
        return True
    except Exception as e:
        print(f"❌ 交易引擎测试失败: {e}")
        traceback.print_exc()
        return False


def test_ai_audit():
    """测试 AI 审计"""
    print("\n" + "=" * 50)
    print("🧠 测试 AI 审计...")
    print("=" * 50)
    
    try:
        from ai_audit import auditor
        from indicators import get_market_summary
        
        market_data = get_market_summary()
        score, report = auditor.audit(market_data)
        
        print(f"AI 评分: {score}")
        if report:
            print(f"报告预览: {report[:100]}...")
        
        print("\n✅ AI 审计测试通过")
        return True
    except Exception as e:
        print(f"❌ AI 审计测试失败: {e}")
        traceback.print_exc()
        return False


def test_risk_manager():
    """测试风险管理"""
    print("\n" + "=" * 50)
    print("💰 测试风险管理...")
    print("=" * 50)
    
    try:
        from risk_manager import (
            calculate_position_size, calculate_take_profit,
            calculate_stop_loss, validate_trade_plan
        )
        
        # 测试仓位计算
        position = calculate_position_size(
            account_balance=10000,
            entry_price=3500,
            stop_loss_price=3400,
            signal_strength=0.5
        )
        print(f"建议仓位: ${position:,.2f}")
        
        # 测试止盈计算
        tp = calculate_take_profit(3500, 3400, 'long')
        print(f"止盈价格: ${tp:,.2f}")
        
        # 测试验证
        valid, msg = validate_trade_plan(3500, 3400, tp, 'long')
        print(f"计划验证: {msg}")
        
        print("\n✅ 风险管理测试通过")
        return True
    except Exception as e:
        print(f"❌ 风险管理测试失败: {e}")
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "🚀 ETH Monitor 模块测试")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_indicators,
        test_trading_engine,
        test_ai_audit,
        test_risk_manager,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n❌ 测试异常: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 测试结果汇总")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 所有测试通过！系统可以正常运行。")
        print("\n启动命令: streamlit run streamlit_app.py")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查相关模块。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
