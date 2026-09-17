# 3. The target is the drift after the call, market-neutral and vol-scaled

**Decision:** `earnings/labels.py` measures from the close of the first trading day after the call, subtracts the benchmark over the same window, and divides by the stock's own pre-call volatility.

**Why:**
- **Starting the day after.** The price reaction to an earnings release happens in minutes. A transcript cannot be read and acted on in time, so including that jump measures something untradeable. What remains is post-earnings announcement drift, which is a documented effect and a falsifiable hypothesis rather than an arbitrary window.
- **Subtracting the benchmark.** A stock up 3% on a day the index rose 3% said nothing about the stock. Without this, a signal that quietly tracks the market looks predictive.
- **Dividing by volatility.** A 2% move in a quiet name is strong evidence; the same move in a violent one is noise. Scaling puts every call in the same units, which is what makes pooling across companies mean anything.
- **Volatility comes strictly from before the call.** Using any price from after the call to scale a return measured after the call leaks the answer into the question.
- Horizons of 1, 3, 5 and 10 days are all computed, so the reported result can be checked against the possibility that the window was the finding.
