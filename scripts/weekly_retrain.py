"""
Script de retreino semanal com notificações Telegram.
Corre automaticamente pelo GitHub Actions todos os Domingos às 03:00.

Uso manual:
  python -m scripts.weekly_retrain
"""

from datetime import date
from scripts.send_telegram import send_dev_message as send_message
from models.rebuild_features import rebuild
from models.train import train as train_1x2
from models.train_markets import train as train_markets


def run():
    today = date.today().strftime("%Y-%m-%d")

    send_message(f"🤖 <b>SharpBet — Retreino Semanal iniciado</b>\n📅 {today}\n\nA reconstruir features...")

    # 1. Rebuild features
    rebuild()

    send_message("⚙️ Features reconstruídas. A treinar modelo 1X2...")

    # 2. Treinar 1X2
    acc_1x2 = train_1x2()

    send_message(f"⚙️ Modelo 1X2 treinado. A treinar BTTS + O/U...")

    # 3. Treinar mercados
    acc_btts, acc_ou = train_markets()

    # 4. Relatório final
    msg = (
        f"✅ <b>SharpBet — Retreino Concluído</b>\n"
        f"📅 {today}\n\n"
        f"📊 <b>Resultados:</b>\n"
        f"  • 1X2 (Resultado Final): <b>{acc_1x2}%</b>\n"
        f"  • Over/Under 2.5: <b>{acc_ou}%</b>\n"
        f"  • BTTS (Ambas Marcam): <b>{acc_btts}%</b>\n\n"
        f"🧠 Modelos atualizados e prontos para a próxima semana!"
    )
    send_message(msg)
    print("\nReatreino concluído e relatório enviado para Telegram.")


if __name__ == "__main__":
    run()
