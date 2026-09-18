# Headline result

165 calls, 5 tickers, 2011-05-18 to 2026-04-30.
14267 speaker turns scored.

## Primary test

Mean turn sentiment against market-neutral, vol-scaled 5-day drift.

    IC -0.009  95% CI [-0.162, +0.144]  p=0.904  n=165  (detectable |IC| >= 0.217)

Significant at 5%: False
Effect found is larger than the smallest detectable: False

## Directional accuracy

    48.5% correct against a 53.3% base rate (-4.8%, p=0.908, n=165)

## Across horizons

If a result shows up at one window only, the window was the finding.

 horizon_days     ic  ci_low  ci_high  p_value   n
            1  0.010  -0.143    0.163    0.894 165
            3 -0.059  -0.210    0.095    0.454 165
            5 -0.009  -0.162    0.144    0.904 165
           10  0.006  -0.147    0.158    0.943 165

## Per ticker

Holm-adjusted for testing several names at once.

ticker     ic  ci_low  ci_high  p_value  n  p_value_holm
  STLA  0.170  -0.424    0.662    0.578 13         1.000
    DE  0.136  -0.124    0.378    0.301 60         1.000
   CCL  0.051  -0.328    0.417    0.795 28         1.000
    AA  0.038  -0.412    0.472    0.875 20         1.000
   MMM -0.248  -0.511    0.057    0.104 44         0.522

## Other ways of combining turns

Fixed before the results were seen: the plain mean is the headline. These
are reported so the choice is visible, not so the best one can be picked.

                  score                               what     ic  ci_low  ci_high  p_value   n
              sentiment           plain mean of every turn -0.009  -0.162    0.144    0.904 165
sentiment_word_weighted weighted by how long each turn was  0.028  -0.126    0.180    0.726 165
   sentiment_management              management turns only  0.033  -0.121    0.185    0.677 165
      sentiment_analyst                 analyst turns only -0.047  -0.199    0.106    0.545 165

## What this sample could have seen

    n=33   detects |IC| >= 0.47 at 80% power, 5% two-sided
    n=165  detects |IC| >= 0.22 at 80% power, 5% two-sided

