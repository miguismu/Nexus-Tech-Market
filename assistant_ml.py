"""Clasificador de intenciones NEXUS basado en TensorFlow (instalación opcional)."""

from __future__ import annotations

_model = None
_labels = ("greeting", "catalog", "buy", "approval", "price", "security", "mission", "help")
_examples = {
    "greeting": ["hola", "buenas tardes", "que tal", "mucho gusto", "buen dia"],
    "catalog": ["quiero ver el catalogo", "busco un computador", "tienen celulares", "ver productos", "necesito una tablet"],
    "buy": ["como compro", "como agrego al carrito", "quiero crear una solicitud", "hacer un pedido", "comprar un producto"],
    "approval": ["como aprueban la compra", "estado de mi solicitud", "donde reviso pedidos", "rechazar una compra", "panel de aprobacion"],
    "price": ["cuanto cuesta", "precio del producto", "cotizacion actual", "valor en pesos", "es un precio real"],
    "security": ["es seguro", "codigo de acceso", "proteccion de datos", "tienen pagos seguros", "como protegen la cuenta"],
    "mission": ["cual es la mision", "vision de nexus", "que significa nexus", "lema del proyecto", "objetivo de la tienda"],
    "help": ["necesito ayuda", "que puedes hacer", "como funciona", "explicame el proyecto", "ayudame por favor"],
}


def predict_intent(message: str) -> str:
    """Entrena un clasificador pequeño local la primera vez y predice la intención."""
    global _model
    import tensorflow as tf

    if _model is None:
        texts = [text for label in _labels for text in _examples[label]]
        targets = [index for index, label in enumerate(_labels) for _ in _examples[label]]
        vectorizer = tf.keras.layers.TextVectorization(
            max_tokens=300, output_mode="int", output_sequence_length=12,
            standardize="lower_and_strip_punctuation",
        )
        vectorizer.adapt(tf.constant(texts))
        _model = tf.keras.Sequential([
            tf.keras.Input(shape=(), dtype=tf.string), vectorizer,
            tf.keras.layers.Embedding(300, 24, mask_zero=True),
            tf.keras.layers.GlobalAveragePooling1D(),
            tf.keras.layers.Dense(24, activation="relu"),
            tf.keras.layers.Dense(len(_labels), activation="softmax"),
        ])
        _model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
        _model.fit(tf.constant(texts), tf.constant(targets), epochs=35, batch_size=8, verbose=0)
    probabilities = _model.predict(tf.constant([message]), verbose=0)[0]
    return _labels[int(probabilities.argmax())]

