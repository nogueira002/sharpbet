import os
from datetime import date, timedelta
from scripts.fetch_fixtures import fetch_todays_fixtures
from scripts.fetch_odds import fetch_odds_for_fixtures
from scripts.analyze import analyze_and_generate_tips
from scripts.update_results import fetch_results, append_to_training_data, run as update_results_run
from scripts.send_telegram import send_message, format_tips_message
from models.database import init_db, get_performance_summary
from config import SUPPORTED_LEAGUE_IDS

TIPS_DIR = "tips"


def save_tips(tips, today_str):
    """Guarda as tips do dia num ficheiro de texto."""
    os.makedirs(TIPS_DIR, exist_ok=True)
    path = os.path.join(TIPS_DIR, f"{today_str}.txt")
    W = 54
    lines = []
    lines.append("=" * W)
    lines.append(f"  SharpBet — Tips do dia {today_str}")
    lines.append(f"  {len(tips)} tip(s) com edge positivo")
    lines.append("=" * W)

    if not tips:
        lines.append("  Nenhuma aposta com edge suficiente hoje.")
    else:
        for i, t in enumerate(tips, 1):
            lines.append(f"\n  #{i}  {t['home_team']} vs {t['away_team']}  [{t['league']}]  {t['date']}")
            lines.append(f"  Mercado  : {t['market']}")
            lines.append(f"  Tip      : {t['tip']}")
            lines.append(f"  Odd      : {t['odd']}")
            lines.append(f"  Bookmaker: {t['implied_probability']}%  -->  Modelo: {t['our_probability']}%")
            lines.append(f"  Edge     : +{t['edge']}%  |  Confianca: {t['confidence']}")
            lines.append(f"  Stake    : {t['stake_pct']}% da banca")
            if t.get("secondary_tips"):
                for e in t["secondary_tips"]:
                    lines.append(f"  Extra    : {e['label']} @{e['odd']}  (Modelo: {e['our_probability']}%  Edge: +{e['edge']}%)")
            lines.append(f"  {'-'*W}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return path


def run():
    today_str = date.today().strftime("%Y-%m-%d")
    W = 54
    init_db()

    print("=" * W)
    print(f"  SharpBet  —  {today_str}")
    print("=" * W)

    # 0. Guardar jogos de hoje já terminados para treino futuro
    finished_today = fetch_results(today_str)
    if finished_today:
        added = append_to_training_data(finished_today)
        if added > 0:
            print(f"  [{added} jogos terminados hoje guardados para treino]\n")

    # 1. Jogos de hoje (ainda por começar)
    print("\nA recolher jogos de hoje...")
    fixtures = fetch_todays_fixtures()

    # Se não há jogos hoje, tentar amanhã
    if not fixtures:
        tomorrow_str = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"  Sem jogos hoje — a verificar amanhã ({tomorrow_str})...")
        fixtures = fetch_todays_fixtures(tomorrow_str)
        if fixtures:
            today_str = tomorrow_str
            print(f"  A mostrar tips para amanhã ({tomorrow_str})")
        else:
            print("Nenhum jogo encontrado para hoje nem amanhã.")
            return

    # Filtrar só as ligas em que o modelo foi treinado
    all_count       = len(fixtures)
    fixtures        = [f for f in fixtures if f.get("league_id") in SUPPORTED_LEAGUE_IDS]
    filtered_count  = all_count - len(fixtures)
    print(f"{all_count} jogos encontrados — {filtered_count} ignorados (liga sem dados) — {len(fixtures)} a analisar.")

    if not fixtures:
        print("Nenhum jogo nas ligas suportadas hoje.")
        return

    # 2. Odds
    print("\nA recolher odds...")
    fixtures_with_odds = fetch_odds_for_fixtures(fixtures)
    if not fixtures_with_odds:
        print("Nenhum jogo com odds disponíveis.")
        return
    print(f"{len(fixtures_with_odds)} jogos com odds.")

    # 3. Análise
    print(f"\nA analisar {len(fixtures_with_odds)} jogos...\n")
    tips = analyze_and_generate_tips(fixtures_with_odds)

    # 4. Resumo no terminal
    print(f"\n{'='*W}")
    print(f"  RESUMO — {len(tips)} tip(s) com edge positivo")
    print(f"{'='*W}")

    if not tips:
        print("  Nenhuma aposta com edge suficiente hoje.\n")
    else:
        for i, t in enumerate(tips, 1):
            print(f"\n  #{i}  {t['home_team']} vs {t['away_team']}  [{t['league']}]")
            print(f"       {t['market']}  —  {t['tip']}  @ {t['odd']}")
            print(f"       Bookmaker: {t['implied_probability']}%  Modelo: {t['our_probability']}%  Edge: +{t['edge']}%")
            print(f"       Stake: {t['stake_pct']}% da banca  |  {t['confidence']}")
            if t.get("secondary_tips"):
                for e in t["secondary_tips"]:
                    print(f"       Extra: {e['label']} @{e['odd']}  (Modelo:{e['our_probability']}%  Edge+{e['edge']}%)")
            print(f"  {'-'*W}")

    # 5. Guardar em ficheiro
    saved_path = save_tips(tips, today_str)
    print(f"\n  Tips guardadas em: {saved_path}")

    # 6. Enviar para Telegram
    msg = format_tips_message(tips, today_str)
    if msg:
        ok = send_message(msg)
        if ok:
            print(f"  Telegram: tips enviadas para o canal ✓")
        else:
            print(f"  Telegram: falha no envio")

    # 6. Mostrar ROI acumulado (se houver dados)
    stats = get_performance_summary()
    if stats:
        print(f"\n  ROI acumulado: {stats['roi']:+.1f}%  "
              f"({stats['wins']}/{stats['total_tips']} tips certas  |  "
              f"lucro: {stats['net_profit']:+.2f}% da banca)")

    print(f"{'='*W}\n")


if __name__ == "__main__":
    run()
