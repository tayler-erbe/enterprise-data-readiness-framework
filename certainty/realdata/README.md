# Real tables, as a control group

Five public tables that each come as a dirty file and a clean file with the same rows: hospital, flights, beers, rayyan and movies. Every cell that differs is a known error with a known correction. 66 columns, 45 with errors, about 18,400 differing cells.

They come from the benchmark set published with the Raha and Baran systems ([github.com/BigDaMa/raha](https://github.com/BigDaMa/raha), Apache-2.0). `fetch.py` downloads them to `data/`, which is not committed. Nothing is redistributed here.

**They are not part of the main test.** They have been public for years and are used in most data-cleaning papers, so a model has probably seen them. They do two jobs:

1. Check that what the detector does on generated errors carries over to real ones.
2. Show what a score looks like on data a model may have memorised.

**Status: downloaded and wired to the harness. No model has been run.**

```bash
cd certainty/realdata
python fetch.py                     # about 11 MB; add --all for the large tax table
python run_real.py --dry-run        # the pipeline, with made-up replies
python run_real.py --base-url http://localhost:8000/v1 --model <model name>
```

Real columns carry no READY, FIXABLE or NEEDS_CONTEXT label, only the cells that differ. So the report scores three simpler things: columns with errors that the model called READY, clean columns it didn't call READY, and whether the cleaned values it wrote match the clean file.

A caution on reading it: most errors in these tables were injected by researchers (letters replaced with "x", for example), so they're real benchmark data and still not the same as errors that arise in a working system.
