"""Learned taste vector: scores candidates by similarity to James's approved aesthetic.
Data lives in pipeline/taste.npz (approved [n,512], rejected [m,512] CLIP embeddings).
Fed automatically: every render saves the chosen clip's embedding (emb_XX.npy);
learn.py record -> approved, learn.py swap -> rejected. Needs >=8 approved to activate."""
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, "taste.npz")


def _load():
    if os.path.exists(STORE):
        d = np.load(STORE)
        return d["approved"], d["rejected"]
    return np.zeros((0, 512), np.float32), np.zeros((0, 512), np.float32)


def add(kind, vecs):
    a, r = _load()
    v = np.asarray(vecs, np.float32).reshape(-1, a.shape[1] if a.size else 512)
    v = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-8)
    if kind == "approved": a = np.vstack([a, v])
    else: r = np.vstack([r, v])
    np.savez_compressed(STORE, approved=a, rejected=r)
    return len(a), len(r)


def ready():
    a, _ = _load()
    return len(a) >= 8


def score(embs):
    """List of embeddings -> 0-100 taste scores (50 = neutral)."""
    a, r = _load()
    if len(a) < 8:
        return [50.0] * len(embs)
    ma = a.mean(0); ma /= np.linalg.norm(ma) + 1e-8
    mr = None
    if len(r) >= 3:
        mr = r.mean(0); mr /= np.linalg.norm(mr) + 1e-8
    out = []
    for e in embs:
        e = np.asarray(e, np.float32).ravel()
        e = e / (np.linalg.norm(e) + 1e-8)
        s = float(e @ ma) - (float(e @ mr) if mr is not None else 0.0)
        out.append(max(0.0, min(100.0, 50 + s * 250)))
    return out
