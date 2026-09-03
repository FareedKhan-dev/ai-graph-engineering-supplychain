"""Semantic layer (Part IV). Needs a CUDA GPU; degrades to a clear skip on CPU.

  embed_texts        BGE-small over a list of strings -> fp16 [n, 384], length-sorted
                     super-shards (the sibling notebook's 17%->100% GPU-util fix).
  build_package_index  embed name + description for every package; memmap the matrix.
  semantic_relevance   question <-> advisory-summary cosine. The signal that separates
                     a REAL exposure from a control pair that shares a concept but not
                     a mechanism (sibling notebook's "aboutness vs polarity").

The model is never asked what is true - only "how similar is this text to that text".
"""

from __future__ import annotations

import os

import numpy as np


def _have_torch():
    try:
        import sentence_transformers  # noqa: F401
        import torch  # noqa: F401

        return True
    except Exception:
        return False


def embed_texts(texts, model_name="BAAI/bge-small-en-v1.5", batch=768, maxlen=256):
    """[n, 384] fp16. Length-sorts so every batch is ~uniform (no padding waste),
    then un-sorts. On a GPU this is the difference between 3.7k and 13k texts/s."""
    if not _have_torch():
        raise RuntimeError(
            "embed_texts needs torch + sentence-transformers on a CUDA GPU. "
            "Install: pip install torch --index-url .../cu128 ; "
            "pip install sentence-transformers"
        )
    import torch
    from sentence_transformers import SentenceTransformer

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")  # fork deadlock, see S15
    m = SentenceTransformer(model_name, device="cuda" if torch.cuda.is_available() else "cpu")
    m.max_seq_length = maxlen
    order = np.argsort([len(t) for t in texts])
    inv = np.empty_like(order)
    inv[order] = np.arange(len(order))
    sub = [texts[i] for i in order]
    vecs = m.encode(
        sub,
        batch_size=batch,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    ).astype(np.float16)
    return vecs[inv]


def build_package_index(store, out_dir, model_name="BAAI/bge-small-en-v1.5", descriptions=None):
    """Embed 'ecosystem/name  <description>' per package -> emb.npy memmap + pkg_ids.npy.
    `descriptions` optional {pkg_id: text}; FULL run pulls it from Libraries.io."""
    from pathlib import Path

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    ids = list(range(len(store.pkg_name)))
    texts = []
    for i in ids:
        d = (descriptions or {}).get(i, "")
        texts.append(f"{store.pkg_eco[i]}/{store.pkg_name[i]}  {d}".strip())
    vecs = embed_texts(texts, model_name)
    np.save(f"{out_dir}/pkg_emb.npy", vecs)
    np.save(f"{out_dir}/pkg_ids.npy", np.asarray(ids, np.int32))
    return {"n": len(ids), "dim": int(vecs.shape[1])}


def semantic_relevance(question, advisory_texts, model_name="BAAI/bge-small-en-v1.5"):
    """cosine(question, each advisory summary). Returns float[k] in [-1, 1]."""
    v = embed_texts([question, *list(advisory_texts)], model_name)
    q, rest = v[0].astype(np.float32), v[1:].astype(np.float32)
    return rest @ q


def relevance_auroc(reals, controls):
    """reals / controls: lists of relevance scores. AUROC of separating them -
    the sibling notebook's 0.948 'real vs control' figure, transplanted."""
    try:
        from sklearn.metrics import roc_auc_score
    except Exception:
        return None
    y = np.r_[np.ones(len(reals)), np.zeros(len(controls))]
    s = np.r_[np.asarray(reals, float), np.asarray(controls, float)]
    return float(roc_auc_score(y, s))


if __name__ == "__main__":
    print("torch+sentence-transformers available:", _have_torch())
    print("This module needs a CUDA GPU. On CPU it raises a clear RuntimeError.")
