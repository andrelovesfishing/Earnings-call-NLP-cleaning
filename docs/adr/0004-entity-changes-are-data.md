# 4. Ticker changes live in a table, not in an if-statement

**Decision:** `TICKER_VALID_FROM` in `earnings/dataset.py` maps a ticker to the date from which it means the company we think it means. Calls before that date are dropped with the reason recorded.

**Why:**
- A ticker is not a company. Alcoa split in November 2016: the name and the ticker `AA` went to the new upstream business, while the original company was renamed Arconic. Joining a 2015 `AA` transcript to today's `AA` price history attaches the wrong company's returns.
- This failure has no symptom. Nothing errors, no value looks strange, and the correlation that comes out the other end is simply wrong.
- Writing it as a table rather than a hardcoded Alcoa check made it cheap to add Stellantis, which did not exist before the FCA/PSA merger in January 2021 and therefore has no earlier price history to join to.
- It remains a list of cases someone had to know about. A real system uses reference data with permanent security identifiers that track entities through corporate actions automatically. The table is the honest version of that at this scale: not a general detector, but at least a visible, testable list rather than a condition buried in a loop.
