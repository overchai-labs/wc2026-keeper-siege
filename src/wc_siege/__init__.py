"""
wc2026-keeper-siege
===================

Did the 48-team 2026 World Cup really produce more goalkeeper "siege" games than
past 32-team tournaments? This package answers that with REAL match data, not a
toy simulation.

The pipeline is five small, ordered steps. Read them in this order:

    collect.py  -> Step 1: pull goalkeeper match logs from FBref (2018/2022/2026)
    clean.py    -> Step 2: reshape into one tidy row per team-per-game
    analyze.py  -> Step 3: build the save/shot distributions and run the stats
    model.py    -> Step 4: (Part 2) fit + VALIDATE an expansion model on real data
    viz.py      -> Step 5: draw the charts for Reddit / LinkedIn

`run.py` at the repo root chains them together.
"""

__version__ = "0.1.0"
