# 6. The Q&A starts at the first analyst, not at a phrase

**Decision:** `find_qa_start` returns the index of the first turn whose speaker is an analyst. Everything before it is prepared remarks and is not scored. Calls with no analyst turn are dropped, with the reason recorded.

**Why:**
- Only the Q&A is worth scoring. Prepared remarks are written days ahead and read aloud, so their tone measures the investor-relations team's drafting, not the state of the business. The answers to questions nobody vetted are the part that can carry information.
- Matching the operator's handover phrase does not work. The wording changes constantly ("we will now begin the question-and-answer session", "afterwards, we will conduct a question and answer session", "we'll proceed with our first question"), and worse, the operator also announces the Q&A in the *opening* boilerplate. A phrase match lands at the top of the call and sweeps in every prepared remark, which is the opposite of what it is for.
- The previous version matched a phrase and, when it failed, fell back to using the entire transcript. That fallback fired on 79 of 174 calls. Nearly half the dataset was scored on prepared remarks plus Q&A while the rest was Q&A alone, and nothing about the output looked wrong.
- Who is speaking is a fact the parser already extracted. What the operator said is a guess about phrasing. Using the fact is both simpler and more robust.
- The cost is that calls without a recognised analyst are lost. These turn out to be genuine presentation-only events with no Q&A, so dropping them is correct rather than merely convenient, but the count is reported on every run so it cannot drift unnoticed.
