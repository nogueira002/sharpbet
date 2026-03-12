"""
Treino do modelo LSTM para previsão de futebol.

Arquitectura:
  Home sequence (10×5) ──→ LSTM(64) ──→ home_encoding (64)
                               ↑ pesos partilhados
  Away sequence (10×5) ──→ LSTM(64) ──→ away_encoding (64)
                                              ↓
                               Concatenate (128)
                                              ↓
                               Dense(64, relu) + Dropout(0.3)
                                              ↓
                               Dense(3, softmax)
                               [P(casa), P(empate), P(fora)]

Pesos LSTM partilhados = o modelo aprende "o que é boa forma de equipa"
e aplica esse conhecimento igualmente para a equipa da casa e de fora.
"""

import os
import sys
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight

# Suprimir mensagens de info do TensorFlow
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
except ImportError:
    print("TensorFlow nao encontrado. Instala com: pip install tensorflow")
    sys.exit(1)

from models.lstm_data import load_sequences

MODEL_PATH = os.path.join(os.path.dirname(__file__), "saved", "lstm_model.keras")


def build_lstm_model(seq_len=10, n_feats=5):
    """
    Constrói o modelo LSTM com pesos partilhados para casa e fora.
    """
    home_input = keras.Input(shape=(seq_len, n_feats), name="home_seq")
    away_input = keras.Input(shape=(seq_len, n_feats), name="away_seq")

    # LSTM partilhado — mesmos pesos para ambas as equipas
    # Isto faz sentido: "aprender forma de equipa" é o mesmo conceito
    shared_lstm = layers.LSTM(64, return_sequences=False, name="shared_lstm")

    home_encoded = shared_lstm(home_input)   # (batch, 64)
    away_encoded = shared_lstm(away_input)   # (batch, 64)

    # Combinar as duas codificações
    combined = layers.Concatenate()([home_encoded, away_encoded])  # (batch, 128)

    x = layers.Dense(64, activation="relu")(combined)
    x = layers.Dropout(0.3)(x)   # Dropout evita overfitting
    x = layers.Dense(32, activation="relu")(x)
    x = layers.Dropout(0.2)(x)

    # Saída: probabilidade de cada resultado
    output = layers.Dense(3, activation="softmax", name="result")(x)

    model = keras.Model(inputs=[home_input, away_input], outputs=output)
    return model


def train():
    print("=" * 52)
    print("  SharpBet — Treino LSTM")
    print("=" * 52)

    # 1. Carregar sequências (force=True reconstrói sempre a partir do raw_fixtures.json)
    print("\nA carregar sequencias...")
    X_home, X_away, y = load_sequences(force=True)

    # 2. Dividir treino/teste (mantendo proporcão de classes)
    idx = np.arange(len(y))
    train_idx, test_idx = train_test_split(
        idx, test_size=0.2, random_state=42, stratify=y
    )
    X_home_tr = X_home[train_idx]; X_away_tr = X_away[train_idx]; y_tr = y[train_idx]
    X_home_te = X_home[test_idx];  X_away_te = X_away[test_idx];  y_te = y[test_idx]

    unique, counts = np.unique(y_tr, return_counts=True)
    print(f"  Treino: Casa={counts[0]}  Empate={counts[1]}  Fora={counts[2]}")

    # 3. Class weights (corrigir desequilíbrio de empates)
    class_weights = compute_class_weight("balanced", classes=np.array([0, 1, 2]), y=y_tr)
    cw = {0: class_weights[0], 1: class_weights[1], 2: class_weights[2]}
    print(f"  Pesos: Casa={cw[0]:.2f}  Empate={cw[1]:.2f}  Fora={cw[2]:.2f}")

    # 4. Construir modelo
    print(f"\nA construir modelo LSTM...")
    model = build_lstm_model()
    print(f"  Parametros treinaveis: {model.count_params():,}")

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    # 5. Callbacks para parar cedo e ajustar learning rate
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_accuracy", patience=12,
            restore_best_weights=True, verbose=1
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5,
            patience=6, verbose=1, min_lr=1e-5
        ),
    ]

    # 6. Treinar
    print(f"\nA treinar (max 150 epochs, para cedo se não melhorar)...\n")
    history = model.fit(
        [X_home_tr, X_away_tr], y_tr,
        validation_data=([X_home_te, X_away_te], y_te),
        epochs=150,
        batch_size=64,
        class_weight=cw,
        callbacks=callbacks,
        verbose=1,
    )

    # 7. Avaliar
    loss, acc = model.evaluate([X_home_te, X_away_te], y_te, verbose=0)
    best_epoch = np.argmax(history.history["val_accuracy"]) + 1
    print(f"\nAccuracy LSTM no teste: {acc:.1%}  (melhor epoch: {best_epoch})")

    from sklearn.metrics import classification_report
    y_pred = np.argmax(model.predict([X_home_te, X_away_te], verbose=0), axis=1)
    print(classification_report(
        y_te, y_pred,
        target_names=["Casa (0)", "Empate (1)", "Fora (2)"],
        zero_division=0
    ))

    # 8. Guardar
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    model.save(MODEL_PATH)
    print(f"Modelo LSTM guardado: {MODEL_PATH}")


if __name__ == "__main__":
    train()
