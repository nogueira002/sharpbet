"""
Envia as tips do dia para o canal Telegram.

Variáveis de ambiente necessárias:
  TELEGRAM_TOKEN   — token do bot (@BotFather)
  TELEGRAM_CHAT_ID — ID do canal (ex: -1003841410691)
"""

import os
import requests


def send_message(text):
    token   = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("  [!] TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID não definidos — a ignorar envio.")
        return False

    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "HTML",
    }
    r = requests.post(url, data=data, timeout=10)
    return r.ok


def format_tips_message(tips, target_date):
    if not tips:
        return None   # Não envia mensagem se não há tips

    lines = []
    lines.append(f"<b>SharpBet — {target_date}</b>")
    lines.append(f"<i>{len(tips)} tip(s) com edge positivo</i>")
    lines.append("")

    for i, t in enumerate(tips, 1):
        conf_emoji = "🔴" if t["confidence"] == "Baixa" else ("🟡" if t["confidence"] == "Media" else "🟢")
        lines.append(f"{conf_emoji} <b>#{i} {t['home_team']} vs {t['away_team']}</b>")
        lines.append(f"🏆 {t['league']}")
        lines.append(f"⏰ {t['date']}")
        lines.append(f"📊 {t['market']} — <b>{t['tip']}</b>")
        lines.append(f"💰 Odd: <b>{t['odd']}</b>")
        lines.append(f"📈 Edge: +{t['edge']}%  |  Modelo: {t['our_probability']}%")
        lines.append(f"💼 Stake: {t['stake_pct']}% da banca")
        if t.get("secondary_tips"):
            for e in t["secondary_tips"]:
                lines.append(f"   ➕ {e['label']} @{e['odd']} (Edge +{e['edge']}%)")
        lines.append("")

    lines.append("⚠️ <i>Aposta com responsabilidade. Isto não é conselho financeiro.</i>")
    return "\n".join(lines)
