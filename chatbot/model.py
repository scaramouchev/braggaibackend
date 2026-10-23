from sentence_transformers import SentenceTransformer

model = None

def get_model():
    global model
    if model is None:
        model = SentenceTransformer(
            "all-MiniLM-L6-v2",
            device="cpu"
        )
    return model