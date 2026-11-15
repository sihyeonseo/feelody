"""Model adapter. Contract: recommend(diary) -> list of top-ranked tracks."""
def build(index, model):
    import feelody_e5 as b1
    rec = b1.Recommender(index, device="cpu")
    if model == "b1":
        predict = lambda text: rec.recommend(text)["recommendations"]
    else:
        import feelody_b3 as b3
        encode = lambda texts, prefix: rec.encoder.encode(texts, prefix, rec.batch_size)[0]
        anchors = encode(list(b3.ANCHORS.values()), "query: ")
        catalog = b3.profiles(rec.matrix, anchors)
        def predict(text):
            v = b3.profiles(encode([text], "passage: "), anchors)[0]
            return b3.winners(rec, catalog @ v)
    def recommend(text):
        return [{k: str(s[k]) for k in ("song_id", "title", "artist")} for s in predict(text)]
    return recommend
