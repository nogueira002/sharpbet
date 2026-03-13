import os
os.environ["TELEGRAM_TOKEN"]   = "8587551716:AAETeMzWvnRX4s2YonhsUgS4mkUW4YZzyRQ"
os.environ["TELEGRAM_CHAT_ID"] = "-1003841410691"

from scripts.send_telegram import send_message, format_tips_message

tips_fake = [
    {
        "home_team":          "Benfica",
        "away_team":          "Porto",
        "league":             "Primeira Liga",
        "date":               "2026-03-13 21:00",
        "market":             "Over/Under 2.5",
        "tip":                "Over 2.5 Golos",
        "odd":                1.85,
        "our_probability":    63.5,
        "implied_probability": 54.1,
        "edge":               9.4,
        "confidence":         "Alta",
        "stake_pct":          4.8,
        "secondary_tips": [],
    }
]

msg = format_tips_message(tips_fake, "2026-03-13")
ok  = send_message(msg)
print("Enviado!" if ok else "Falhou")
