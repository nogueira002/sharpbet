import schedule
import time
from scripts.fetch_fixtures import fetch_todays_fixtures
from scripts.fetch_odds import fetch_odds_for_fixtures
from scripts.analyze import analyze_and_generate_tips

def run_pipeline():
    print("🔄 A recolher jogos de hoje...")
    fixtures = fetch_todays_fixtures()

    print(f"✅ {len(fixtures)} jogos encontrados. A recolher odds...")
    fixtures_with_odds = fetch_odds_for_fixtures(fixtures)

    print("🧠 A analisar e gerar tips...")
    tips = analyze_and_generate_tips(fixtures_with_odds)

    print(f"✅ {len(tips)} tips geradas com edge positivo.")

if __name__ == "__main__":
    # Corre imediatamente ao iniciar
    run_pipeline()

    # Agenda para correr todos os dias às 8h
    schedule.every().day.at("08:00").do(run_pipeline)

    print("⚡ SharpBet a correr. À espera do próximo ciclo...")
    while True:
        schedule.run_pending()
        time.sleep(60)