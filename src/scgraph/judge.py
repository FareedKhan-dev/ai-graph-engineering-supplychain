"""A small, honest wrapper around a local instruct model, used ONLY as a measurement
instrument (Part VIII S25) - never in the alerting path.

  load_judge(name, four_bit=True)  -> a dict {tok, model, name}
  ask_band(J, summary, cvss_vector) -> one of Critical/High/Medium/Low/None

The model is asked a question with a *known* answer (the CVSS band, which we computed
deterministically from the vector in S1). If it cannot recover the band even when handed
the vector (oracle), the instrument is broken and every judge-derived number is suspect.

GPU box only. `load_judge` raises a clear RuntimeError on CPU / missing deps.
"""

from __future__ import annotations

import re

_BANDS = ("Critical", "High", "Medium", "Low", "None")


def _have():
    try:
        import transformers  # noqa: F401

        return True
    except Exception:
        return False


def load_judge(name="Qwen/Qwen3-14B", four_bit=True, max_new_tokens=24):
    if not _have():
        raise RuntimeError("judge needs torch + transformers on a CUDA GPU")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("judge needs CUDA")
    tok = AutoTokenizer.from_pretrained(name)
    kw = {"dtype": torch.bfloat16, "device_map": "cuda"}
    if four_bit:
        try:
            from transformers import BitsAndBytesConfig

            kw = {
                "device_map": "cuda",
                "quantization_config": BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                    bnb_4bit_quant_type="nf4",
                ),
            }
        except Exception:
            pass
    model = AutoModelForCausalLM.from_pretrained(name, **kw)
    model.eval()
    dev = next(model.parameters()).device
    return {"tok": tok, "model": model, "name": name, "mnt": max_new_tokens, "dev": dev}


def _gen(J, prompt):
    import torch

    tok, model, dev = J["tok"], J["model"], J["dev"]
    msgs = [
        {
            "role": "system",
            "content": "You are a terse security analyst. "
            "Answer with exactly one word from the given options.",
        },
        {"role": "user", "content": prompt},
    ]
    kw = {"add_generation_prompt": True, "return_tensors": "pt", "return_dict": True}
    try:
        enc = tok.apply_chat_template(msgs, enable_thinking=False, **kw)
    except (TypeError, ValueError):
        enc = tok.apply_chat_template(msgs, **kw)
    enc = {k: v.to(dev) for k, v in enc.items()}
    n_in = enc["input_ids"].shape[1]
    with torch.no_grad():
        out = model.generate(
            **enc, max_new_tokens=J["mnt"], do_sample=False, pad_token_id=tok.eos_token_id
        )
    txt = tok.decode(out[0, n_in:], skip_special_tokens=True)
    # if the model still emitted a <think> block, keep only what follows </think>
    if "</think>" in txt:
        txt = txt.split("</think>", 1)[1]
    return txt.strip()


def ask_band(J, summary, cvss_vector=None):
    """cvss_vector None -> blind arm; a string -> oracle arm."""
    ev = f"\nCVSS vector: {cvss_vector}" if cvss_vector else ""
    p = (
        f"Advisory summary: {str(summary)[:500]}{ev}\n\n"
        f"What is this vulnerability's CVSS base severity band? "
        f"Options: Critical, High, Medium, Low, None. One word:"
    )
    raw = _gen(J, p)
    for b in _BANDS:
        if re.search(rf"\b{b}\b", raw, re.I):
            return b
    return "Medium"  # unparseable -> the neutral guess (counts against the model)


if __name__ == "__main__":
    print("judge available:", _have(), "- CUDA GPU only")
