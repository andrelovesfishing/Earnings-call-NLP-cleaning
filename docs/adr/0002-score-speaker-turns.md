# 2. Sentiment is scored per speaker turn, then combined

**Decision:** `ChunkScorer.score` runs on one speaker turn at a time. `aggregate` combines turn scores into one number per call, reading from a cache.

**Why:**
- The model reads 512 tokens. A call's Q&A runs to twenty thousand. Passing the call as one string scores the first two pages and silently discards the rest, which is most of it.
- Turns are short enough to survive whole, so the whole call is actually read.
- Splitting the expensive step from the combining step means the model runs once. Every question about how to combine turns (plain mean, weighted by length, management only, analysts only) is then arithmetic over a small cached file, and costs nothing.
- The cache is append-only JSONL, flushed per call, so an interrupted run resumes instead of restarting.
- Turn-level scores also keep the speaker's role attached, which is what makes the management-versus-analyst split possible at all.
