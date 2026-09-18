# How many earnings calls would it take to know if tone predicts returns?

Executives answer analysts unscripted for half an hour, and the tone of those answers might carry something the market hasn't priced yet. Any effect like that would be small, and small effects need a lot of calls before they show up at all. So I tried to quantify how many.

I started by taking 165 earnings calls and tested how strong a return signal I could get from the tone of the Q&A. At that sample size, the test can only reliably detect a correlation of 0.22 or larger. To have a realistic shot at seeing a signal worth trading, the sample would need to be roughly 3,100 calls.

The 165 measured result, nothing of value: IC -0.009, p = 0.90.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/power-curve-dark.svg">
  <img alt="Smallest detectable effect against sample size. The curve falls steeply from about 0.59 at 20 calls to 0.22 at 165 calls, then flattens: reaching an IC of 0.21 needs roughly 175 calls, and going meaningfully below that needs many hundreds. This study sits at 165 calls, detecting 0.22." src="docs/figures/power-curve-light.svg" width="720">
</picture>

## Overview

- Parsed 174 PDF transcripts into speaker turns, keeping who was talking and in what role.
- Scored only the Q&A, turn by turn, because prepared remarks are written days ahead by the investor-relations team.
- Measured drift over the following days rather than the jump on the day, stripped out the market, and scaled by each stock's own volatility.
- Fixed the headline test and the power calculation before running the model once, so there was no room to go looking for a result afterwards.
- 77 tests, and every design decision written up in [docs/adr](docs/adr/).

## How it works

Turning that idea into a number takes four steps.

**Score the right part of the call.** Prepared remarks are drafted in advance and read aloud, so their tone measures the IR team's writing, not the business. Only the Q&A is worth scoring. Finding where it starts is harder than it sounds, and getting it wrong quietly wrecks the result — see below.

**Score turn by turn.** FinBERT is a language model trained on financial text; it reads 512 tokens at a time, and a Q&A session runs to twenty thousand words. So each speaker turn is scored separately and the call's score is the average. Turn scores are cached, which means every alternative way of combining them costs nothing to try.

**Measure the right thing.** The price jump when results are announced is gone in seconds and isn't tradeable from a transcript you read afterwards. So the target is *drift*: what the stock does over the following 1, 3, 5 and 10 days, starting from the close of the day after the call. The market's own move is subtracted out, and the result is divided by the stock's volatility so a quiet name and a jumpy one count equally.

**Ask whether the answer means anything.** The measure is the information coefficient, or IC: the rank correlation between what the score predicted and what actually happened. Zero is no relationship. An IC of 0.05 sustained across a wide universe is a genuinely useful signal in practice. The catch is that small samples can't see small effects, so before running anything I worked out what this one could see: 0.22. Anything smaller would be invisible here whether it exists or not.

## Results

The headline test, fixed in advance: mean turn sentiment against 5-day drift.

```
IC -0.009    95% CI [-0.162, +0.144]    p = 0.90    n = 165
```

Direction alone is no better: 48.5% of calls called correctly, against a 53.3% base rate.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/ic-by-horizon-dark.svg">
  <img alt="Information coefficient at four horizons with 95% confidence intervals. 1 day +0.01, 3 days -0.06, 5 days -0.01, 10 days +0.01. Every interval spans roughly -0.2 to +0.16 and every one crosses zero." src="docs/figures/ic-by-horizon-light.svg" width="720">
</picture>

Nothing appears anywhere else either:

| Cut | Result |
|---|---|
| Other horizons | IC between -0.06 and +0.01, every p above 0.45 |
| Other ways of averaging turns | word-weighted +0.03, management only +0.03, analysts only -0.05 |
| Per company | 3M is the largest at -0.25 (p = 0.10), which becomes p = 0.52 once corrected for testing five names |

The alternatives are listed because I ran them, not so the best one could be promoted. The plain mean was the headline before I saw any of it. Full output in [docs/headline.md](docs/headline.md).

## What I got wrong

The Q&A boundary was the thing that nearly ruined this, twice.

The first version looked for the operator's handover phrase. The wording varies constantly, and the operator also mentions the Q&A in the opening boilerplate, so the match often landed at the top of the call. When it failed entirely, it fell back to scoring the whole transcript. That fallback fired on 79 of 174 calls. Half the dataset was scored on prepared remarks plus Q&A and half on Q&A alone, and nothing about the output looked wrong. Prepared remarks are relentlessly upbeat, so this added a company-specific bias to the exact thing being measured.

I replaced it with a structural rule: the Q&A starts at the first analyst turn, because who is speaking is a fact in the document, not a guess about phrasing. That was a real improvement, and it still had a bug. It identified analysts by looking for the word "Analyst" in their job title, and plenty of analysts don't have it — "Senior Director, Bank of America", "Head of European Automotive Investment Research, Goldman Sachs". Nine calls were dropped as having no Q&A at all. Eight were Stellantis, and specifically its half-year and full-year calls.

That is the part worth noticing. The loss wasn't random: it landed on one company and one kind of call, which is exactly the bias the rule was written to remove. The run had been reporting them as "no speaker turns parsed", which was also false — those transcripts parse fine. Both are fixed, the drops are still reported on every run, and [ADR 0006](docs/adr/0006-qa-boundary-is-structural.md) now records what they actually are.

Both bugs were silent. Nothing errored and every number looked plausible, which is why the count of what gets dropped, and why, is printed on every run.

## Limitations

- **Five companies.** 3M, Deere, Carnival, Alcoa and Stellantis, 2011 to 2026. That is a handful of names over a long stretch, not a cross-section, and it is the binding constraint on everything above.
- **165 calls can only see an effect of 0.22.** Getting down to 0.05 takes about 3,100, which means an automated transcript source rather than hand-collected PDFs.
- **Nine calls are still dropped** because their Q&A boundary can't be located, eight of them Stellantis. Fixing the parser to segment those speakers properly would recover them.
- **No earnings-surprise control.** Tone and the size of the beat or miss move together, so some of what is being measured here is probably the surprise, not the tone.
- **FinBERT is used as it comes.** With fewer than 200 calls there is nothing to fine-tune on, and a train/test split would have cost most of the sample. [ADR 0001](docs/adr/0001-no-fine-tuning.md).

## What I'd do next

Widen the universe before anything else; nothing here is worth refining at n=165. After that, sector-neutralise the returns, control for the earnings surprise so tone is measured on top of it rather than alongside it, and walk the test forward in time instead of pooling.

## Running it

Requires Python 3.11+. Transcripts are licensed and not included.

```
pip install -e ".[dev]"
pytest                                    # 77 tests
python -m experiments.build_dataset --parse --pdf-dir transcripts_pdf_archive
python -m experiments.score               # the only slow step, resumable
python -m experiments.headline
python docs/figures/power_curve.py        # README figures
python docs/figures/ic_by_horizon.py
```

`score` caches every call as it finishes, so stopping it costs nothing — it picks up where it left off. Design decisions are in [docs/adr](docs/adr/).
