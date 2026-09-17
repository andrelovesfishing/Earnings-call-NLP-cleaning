# 1. FinBERT is used as it comes, not fine-tuned

**Decision:** `earnings/sentiment.py` runs the pretrained model and never trains. There is no training set, no validation split and no saved checkpoint.

**Why:**
- FinBERT has 110 million parameters. There are fewer than 200 labelled calls. Nothing useful is learned from that, and the attempt is what consumed the data.
- Training needs a train/test split. An 80/20 split left 33 calls to measure on, and 33 calls can only reliably detect a correlation above about 0.47. Nothing in this literature is that large, so the test could not have found a real effect even if one existed.
- With no training, every call is a measurement. That is a fivefold increase in the sample the result rests on, for free, and it takes the smallest detectable correlation down to about 0.21.
- A fixed model has no hyperparameters to tune, so there is no way to overfit the sample by accident.
- The cost is that the model was never told what earnings-call optimism looks like in *this* dataset. That is a real limitation and it is stated in the README, not hidden.
