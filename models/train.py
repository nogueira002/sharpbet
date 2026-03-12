"""
Treino do modelo XGBoost v2.

Melhorias vs v1:
  - 26 features (era 12)
  - Class balancing (corrige o problema de prever poucos empates)
  - Melhores hiperparâmetros (500 árvores, learning rate mais baixo)
  - Feature importance — mostra quais features mais importam
"""

import os
import numpy as np
import pandas as pd
import joblib
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.utils.class_weight import compute_sample_weight

DATA_PATH  = os.path.join(os.path.dirname(__file__), "saved", "training_data.csv")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "saved", "xgboost_model.pkl")


def train():
    # 1. Carregar dados
    print("A carregar dados de treino...")
    df = pd.read_csv(DATA_PATH)
    print(f"  {len(df)} jogos | {len(df.columns)-1} features")

    X = df.drop(columns=["result"]).values
    y = df["result"].values

    # 2. Dividir: 70% treino | 10% calibração | 20% teste
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, random_state=42, stratify=y
    )
    X_cal, X_test, y_cal, y_test = train_test_split(
        X_temp, y_temp, test_size=2/3, random_state=42, stratify=y_temp
    )
    print(f"  Treino: {len(X_train)} | Calibracao: {len(X_cal)} | Teste: {len(X_test)}")

    # 3. Class balancing
    # O modelo vê poucos empates → damos mais peso a empates e resultados fora
    # compute_sample_weight('balanced') calcula pesos automaticamente
    sample_weights = compute_sample_weight("balanced", y_train)

    unique, counts = np.unique(y_train, return_counts=True)
    print(f"\n  Distribuicao treino: Casa={counts[0]}  Empate={counts[1]}  Fora={counts[2]}")
    print(f"  Pesos aplicados   : Casa={sample_weights[y_train==0].mean():.2f}  "
          f"Empate={sample_weights[y_train==1].mean():.2f}  "
          f"Fora={sample_weights[y_train==2].mean():.2f}")

    # 4. Treinar XGBoost
    print("\nA treinar XGBoost (500 arvores)...")
    model = XGBClassifier(
        n_estimators=500,
        max_depth=5,
        learning_rate=0.05,       # mais lento mas mais preciso
        subsample=0.8,            # usa 80% dos dados por árvore (evita overfitting)
        colsample_bytree=0.8,     # usa 80% das features por árvore
        min_child_weight=3,       # evita overfitting em amostras pequenas
        gamma=0.1,                # regularização
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42,
        verbosity=0,
    )
    model.fit(X_train, y_train, sample_weight=sample_weights)
    print("  Treino concluido!")

    # 5. Calibrar probabilidades (isotonic regression no conjunto de calibração)
    # Isto corrige o problema das probabilidades constantes/desajustadas
    print("A calibrar probabilidades...")
    calibrated_model = CalibratedClassifierCV(model, method="isotonic", cv=None)
    calibrated_model.fit(X_cal, y_cal)
    print("  Calibracao concluida!")

    # 6. Avaliar modelo calibrado
    y_pred = calibrated_model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\nAccuracy no conjunto de teste: {acc:.1%}")
    print(classification_report(
        y_test, y_pred,
        target_names=["Casa (0)", "Empate (1)", "Fora (2)"],
        zero_division=0,
    ))

    # Mostrar probabilidades médias calibradas vs frequências reais
    probs = calibrated_model.predict_proba(X_test)
    print("Calibracao — probabilidade media prevista vs frequencia real:")
    labels_cal = ["Casa", "Empate", "Fora"]
    for i, lbl in enumerate(labels_cal):
        freq_real = (y_test == i).mean()
        prob_med  = probs[:, i].mean()
        print(f"  {lbl}: previsto={prob_med:.1%}  real={freq_real:.1%}")

    # 7. Feature importance — top 10
    feature_names = pd.read_csv(DATA_PATH).drop(columns=["result"]).columns.tolist()
    importances   = model.feature_importances_
    top = sorted(zip(feature_names, importances), key=lambda x: -x[1])[:10]
    print("Top 10 features mais importantes:")
    for name, imp in top:
        bar = "█" * int(imp * 200)
        print(f"  {name:<35} {imp:.4f}  {bar}")

    # 8. Guardar modelo calibrado
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(calibrated_model, MODEL_PATH)
    print(f"\nModelo calibrado guardado em: {MODEL_PATH}")


if __name__ == "__main__":
    train()
