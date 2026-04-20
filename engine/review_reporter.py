"""
Phase 4.1b: 复盘报告生成与推送
- 生成格式化复盘报告（文字摘要 + 关键数据）
- 推送至飞书群组
- 保存至 reports/ 目录
"""

import json
import logging
import requests
from datetime import datetime
from typing import Optional
from engine.auto_review import run_review, AutoReviewEngine

logger = logging.getLogger("ReviewReporter")

# 飞书群组 Webhook（从环境变量读取）
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/oc_4a9f5bf64492437054d80cebac4f5568"


class ReviewReporter:
    """
    复盘报告生成与推送。
    每日收盘后（16:00后）由 cron 触发，或手动调用。
    """

    def __init__(self, webhook_url: str = FEISHU_WEBHOOK):
        self.webhook_url = webhook_url

    def generate_text_report(self, review_result: dict) -> str:
        """生成文字报告摘要"""
        summary = review_result.get("summary", {})
        date_str = summary.get("date", datetime.now().strftime("%Y-%m-%d"))
        ai_results = review_result.get("ai_results", {})

        lines = [
            f"📊 **AI股神争霸 · 每日复盘** `{date_str}`",
            "=" * 40,
            f"参赛AI数: {summary.get('ai_count', 0)}",
            f"总资产: {summary.get('total_value_all', 0):,.2f}",
            f"平均收益: {summary.get('avg_return_pct', 0)*100:+.2f}%",
            "",
            "🏆 **收益排行**",
        ]

        # 收益排行（前3名和后3名）
        rankings = summary.get("rankings", [])
        for r in rankings:
            rank_emoji = {
                1: "🥇",
                2: "🥈",
                3: "🥉",
            }.get(r["rank"], f"#{r['rank']}")
            flag = "⚠️" if r["signal"] != "OK" else ""
            ret = r["return_pct"] * 100
            lines.append(
                f"  {rank_emoji} {r['ai_name']}: {ret:+.2f}%{flag}"
            )

        # 策略预警
        adjust_needed = summary.get("adjust_needed", [])
        if adjust_needed:
            lines.append("")
            lines.append("⚠️ **策略调整建议**")
            for a in adjust_needed:
                lines.append(f"  • {a['ai_name']}: {a['reason']}")

        # 重点浮盈/浮亏持仓
        lines.append("")
        lines.append("💰 **持仓浮盈 TOP3**")
        all_holdings = []
        for ai_id, r in ai_results.items():
            for h in r.get("holdings", []):
                all_holdings.append({
                    "ai_name": r["ai_name"],
                    **h
                })
        all_holdings.sort(key=lambda x: x["unrealized_pnl"], reverse=True)
        for h in all_holdings[:3]:
            pnl_pct = h["unrealized_pnl_pct"] * 100
            pnl_abs = h["unrealized_pnl"]
            emoji = "📈" if pnl_abs >= 0 else "📉"
            lines.append(
                f"  {emoji} {h['ai_name']} {h['symbol']} {h['name']}: "
                f"{pnl_abs:+,.0f}({pnl_pct:+.2f}%)"
            )

        if all_holdings:
            lines.append("")
            lines.append("💸 **持仓浮亏 TOP3**")
            for h in sorted(all_holdings, key=lambda x: x["unrealized_pnl"])[:3]:
                pnl_pct = h["unrealized_pnl_pct"] * 100
                pnl_abs = h["unrealized_pnl"]
                lines.append(
                    f"  📉 {h['ai_name']} {h['symbol']} {h['name']}: "
                    f"{pnl_abs:+,.0f}({pnl_pct:+.2f}%)"
                )

        lines.append("")
        lines.append("───")
        lines.append(f"生成时间: {datetime.now().strftime('%H:%M:%S')}")

        return "\n".join(lines)

    def push_to_feishu(self, text: str) -> bool:
        """推送文字报告到飞书群组"""
        payload = {
            "msg_type": "text",
            "content": {"text": text}
        }
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("[ReviewReporter] 飞书推送成功")
                return True
            else:
                logger.error(f"[ReviewReporter] 飞书推送失败: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"[ReviewReporter] 飞书推送异常: {e}")
            return False

    def push_rich_report(self, review_result: dict) -> bool:
        """推送富文本报告到飞书（使用 interactive 卡片）"""
        summary = review_result.get("summary", {})
        date_str = summary.get("date", datetime.now().strftime("%Y-%m-%d"))
        rankings = summary.get("rankings", [])
        ai_results = review_result.get("ai_results", {})

        # 构建排行行
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}
        rank_elements = []
        for r in rankings:
            emoji = medal.get(r["rank"], f"#{r['rank']}")
            flag = " ⚠️" if r["signal"] != "OK" else ""
            ret = r["return_pct"] * 100
            rank_elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"{emoji} **{r['ai_name']}** `{ret:+.2f}%`{flag}"
                }
            })

        # 持仓浮盈TOP3
        all_holdings = []
        for ai_id, r in ai_results.items():
            for h in r.get("holdings", []):
                all_holdings.append({"ai_name": r["ai_name"], **h})
        all_holdings.sort(key=lambda x: x["unrealized_pnl"], reverse=True)

        holding_elements = []
        for h in all_holdings[:3]:
            pnl = h["unrealized_pnl"]
            pct = h["unrealized_pnl_pct"] * 100
            holding_elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"📈 **{h['ai_name']}** {h['symbol']} {h['name']}: `{pnl:+,.0f}` `({pct:+.2f}%)`"
                }
            })

        # 策略调整建议
        adjust_needed = summary.get("adjust_needed", [])
        adjust_elements = []
        if adjust_needed:
            for a in adjust_needed:
                adjust_elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"⚠️ **{a['ai_name']}**: {a['reason']}"
                    }
                })
        else:
            adjust_elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": "✅ 所有AI策略运行正常"}
            })

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"📊 AI股神争霸 · 每日复盘 {date_str}"},
                    "template": "purple" if summary.get("avg_return_pct", 0) >= 0 else "red"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": (
                                f"**参赛AI**: {summary.get('ai_count', 0)} 个\n"
                                f"**总资产**: {summary.get('total_value_all', 0):,.0f}\n"
                                f"**平均收益**: {summary.get('avg_return_pct', 0)*100:+.2f}%"
                            )
                        }
                    },
                    {"tag": "hr"},
                    {"tag": "div", "text": {"tag": "plain_text", "content": "🏆 收益排行", "lang": "zh_cn"}},
                    *rank_elements,
                    {"tag": "hr"},
                    {"tag": "div", "text": {"tag": "plain_text", "content": "💰 持仓浮盈 TOP3", "lang": "zh_cn"}},
                    *holding_elements,
                    {"tag": "hr"},
                    {"tag": "div", "text": {"tag": "plain_text", "content": "⚠️ 策略状态", "lang": "zh_cn"}},
                    *adjust_elements,
                    {
                        "tag": "note",
                        "elements": [
                            {"tag": "plain_text", "content": f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
                        ]
                    }
                ]
            }
        }

        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("[ReviewReporter] 飞书富文本卡片推送成功")
                return True
            else:
                logger.error(f"[ReviewReporter] 飞书推送失败: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"[ReviewReporter] 飞书推送异常: {e}")
            return False

    def run_and_push(self, date_str: str = None) -> dict:
        """运行复盘并推送报告"""
        # 1. 运行复盘
        logger.info("[ReviewReporter] 开始生成复盘报告...")
        review_result = run_review(date_str)

        # 2. 生成文字报告
        text_report = self.generate_text_report(review_result)
        print(text_report)

        # 3. 推送飞书
        feishu_ok = self.push_to_feishu(text_report)

        # 4. 尝试富文本卡片（备用）
        if not feishu_ok:
            logger.info("[ReviewReporter] 尝试富文本卡片推送...")
            self.push_rich_report(review_result)

        return {
            "date": review_result["date"],
            "feishu_ok": feishu_ok,
            "report": text_report,
        }


def main(date_str: str = None):
    reporter = ReviewReporter()
    result = reporter.run_and_push(date_str)
    return result


if __name__ == "__main__":
    import sys
    date_str = sys.argv[1] if len(sys.argv) > 1 else None
    main(date_str)
