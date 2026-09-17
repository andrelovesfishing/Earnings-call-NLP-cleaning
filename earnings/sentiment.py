"""FinBERT sentiment, one speaker turn at a time.

Scoring a turn at a time rather than the whole call fixes a hard limit: the
model reads 512 tokens and an earnings call Q&A runs to twenty thousand, so
feeding it the call as one string shows it the first two pages and discards the
rest. Turns are short enough to survive whole.

The expensive pass writes a score per turn to disk. Everything after that,
including every choice about how to combine turns into one number per call, is
arithmetic on a small cached file. Aggregation choices are free to explore; the
model only ever runs once.

The score is P(positive) - P(negative), with the positions of those two classes
read from the model's own label map rather than assumed. FinBERT orders its
labels positive, negative, neutral, so the obvious guess is off by a sign.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

MODEL_NAME = "ProsusAI/finbert"
MAX_TOKENS = 512
BATCH_SIZE = 16

MANAGEMENT_ROLES = ("CEO", "CFO", "COO", "CTO", "President", "Chairman", "Chief", "EVP", "VP")


@dataclass
class ChunkScorer:
    """FinBERT held open across calls, so the weights load once."""

    model_name: str = MODEL_NAME
    batch_size: int = BATCH_SIZE

    def __post_init__(self) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self._model.eval()

        labels = {v.lower(): int(k) for k, v in self._model.config.id2label.items()}
        try:
            self._positive, self._negative = labels["positive"], labels["negative"]
        except KeyError as exc:
            raise RuntimeError(f"{self.model_name} has no positive/negative class: {labels}") from exc

    def score(self, texts: list[str]) -> np.ndarray:
        """P(positive) - P(negative) for each text, in [-1, 1]."""
        if not texts:
            return np.array([], dtype=float)

        out = []
        with self._torch.inference_mode():
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start : start + self.batch_size]
                encoded = self._tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=MAX_TOKENS,
                    return_tensors="pt",
                )
                probs = self._torch.softmax(self._model(**encoded).logits, dim=-1)
                out.append((probs[:, self._positive] - probs[:, self._negative]).numpy())
        return np.concatenate(out)


def _is_management(role: str) -> bool:
    return any(token in role for token in MANAGEMENT_ROLES)


def score_transcripts(
    json_dir: str,
    calls: pd.DataFrame,
    cache_path: str,
    scorer: ChunkScorer | None = None,
    progress: bool = True,
) -> None:
    """Score every turn of every call, appending to a JSONL cache.

    Calls already in the cache are skipped, so an interrupted run resumes. One
    call is held in memory at a time.
    """
    from earnings.dataset import load_chunks

    done: set[str] = set()
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as handle:
            done = {json.loads(line)["source_file"] for line in handle if line.strip()}

    todo = [f for f in calls["source_file"] if f not in done]
    if not todo:
        return

    scorer = scorer or ChunkScorer()
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)

    with open(cache_path, "a", encoding="utf-8") as handle:
        for i, source_file in enumerate(todo, 1):
            chunks = load_chunks(json_dir, source_file)
            scores = scorer.score([c["text"] for c in chunks])
            handle.write(
                json.dumps(
                    {
                        "source_file": source_file,
                        "scores": [round(float(s), 6) for s in scores],
                        "roles": [c.get("speaker_role", "Unknown") for c in chunks],
                        "n_words": [len(c["text"].split()) for c in chunks],
                    }
                )
                + "\n"
            )
            handle.flush()
            if progress:
                print(f"  [{i}/{len(todo)}] {source_file}  ({len(chunks)} turns)", flush=True)


def aggregate(cache_path: str) -> pd.DataFrame:
    """Turn-level scores into one row per call.

    `sentiment` is the headline: the plain mean across every turn. The rest are
    alternatives, reported as robustness rather than picked from.
    """
    rows = []
    with open(cache_path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            scores = np.array(record["scores"], dtype=float)
            if len(scores) == 0:
                continue

            roles = record["roles"]
            words = np.array(record["n_words"], dtype=float)
            is_mgmt = np.array([_is_management(r) for r in roles])

            rows.append(
                {
                    "source_file": record["source_file"],
                    "sentiment": scores.mean(),
                    "sentiment_word_weighted": float(np.average(scores, weights=np.maximum(words, 1))),
                    "sentiment_management": scores[is_mgmt].mean() if is_mgmt.any() else np.nan,
                    "sentiment_analyst": scores[~is_mgmt].mean() if (~is_mgmt).any() else np.nan,
                    "n_scored_turns": len(scores),
                }
            )

    return pd.DataFrame(rows)
