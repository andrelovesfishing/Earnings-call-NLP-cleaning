# 5. Nothing is dropped without a reason attached

**Decision:** `load_calls` returns a `CallSet` holding what it kept *and* what it discarded, each with a `drop_reason`. The parser attaches a `parse_report` to every transcript recording what it could not classify.

**Why:**
- The previous version filtered on a dictionary lookup. Eleven transcripts had no company name, fell out silently, and stayed out. Nobody noticed because the pipeline ran fine and the results looked plausible.
- The cause turned out to be one regex: Quartr writes `Q1 2021 TU - 5 May, 2021` on a trading update, and the header pattern only allowed the quarter to be followed immediately by the dash. A visible drop count would have found that in minutes.
- Making losses part of the return value means the count appears in the run output every time, so a dataset that quietly halves is noticed before it reaches a result.
- The same reasoning applies to speaker roles. Unmatched prefixes are recorded rather than guessed at, so a transcript format the parser has never seen shows up as a number instead of as bad labels.
- A pipeline that reports its own failure rate is the difference between a result you can defend and one you merely have.
