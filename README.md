# wc2026-keeper-siege

**Did the 48-team 2026 World Cup really bury goalkeepers more often than the old 32-team tournaments? Answered with real match data, not a toy model.**

The 2026 World Cup became "the goalkeepers' World Cup": Cape Verde's 40-year-old
Vozinha denying Spain, Curaçao's Eloy Room making 15 saves in one game, minnows
hanging on for dear life. The natural question: is that just vibes, or did
expanding the field from 32 to 48 teams **structurally** produce more one-sided,
keeper-burying games?

This repo answers it honestly:

- **Real data.** Per-game goalkeeper logs for 2018, 2022 and 2026, pulled from FBref.
- **Full distribution, no cherry-picked threshold.** We plot the whole shape of
  per-game "siege load" and show the 6/8/10-save cutoffs only as a sensitivity check.
- **Two signals, not one.** Saves *and* shots-on-target-against — because a 74%-possession
  battering can produce few saves (hello, Spain 0–0 Cape Verde) and still be a siege.
- **A statistical test**, not an eyeballed gap.

> Why so careful? An earlier version of this analysis used a Monte-Carlo *simulation*
> and got (rightly) taken apart on r/dataisbeautiful for modelling data that already
> existed. This rewrite does it the way the critics asked. The best objections from
> that thread are baked into the method here.

---

## Results

Group stage only: **2018 + 2022 (32-team, 96 games)** vs **2026 (48-team, 72 games)**.
For each game we take the more-besieged keeper (the higher of the two keepers' values).

We test **three** ways of measuring a siege — and report all three, always. Showing only
the one that reached p<0.05 would be metric-shopping, the same mistake as picking the save
cutoff that flatters the story.

| Per-game siege load (besieged keeper) | 32-team era | 2026 | p (2026 higher) | p<0.05 | survives Bonferroni (0.017)? |
|---|---|---|---|---|---|
| **Saves** | 3.62 | 3.89 | 0.42 | no | no |
| **Shots on target faced** | 5.18 | 5.97 | **0.035** | **yes** | **no** |
| **Total shots faced** | 15.23 | 16.60 | 0.14 | no | no |

![siege distribution — shots on target](figures/siege_distribution_max_sota.png)

**The honest takeaway — which contradicts the viral "sieges tripled" framing:**

- **All three measures point the same way**: 2026 keepers face more. The direction is
  consistent, and that consistency is the real signal.
- **But only one clears p<0.05, and it does not survive multiple-comparison correction.**
  With three correlated tests the Bonferroni bar is 0.05/3 = 0.017, and SoTA's 0.035 misses
  it. So this is **suggestive, not established**. Anyone claiming a proven effect at these
  sample sizes (72 vs 96 games) is overreading.
- **Saves are the wrong instrument.** 2026 keepers face more but don't *save* more, because
  extra shots against weaker sides go *in* rather than being stopped. The viral "record
  saves" story is built on a few heroic tail games, not a shift in the distribution.

**Why "total shots faced" had to be added** — this answers the sharpest Reddit objection.
Spain 0–0 Cape Verde was a textbook siege (74% possession, 27 shots, 2.1 xG), yet Vozinha
made only **7 saves off 7 shots on target**, because most of Spain's shots missed or were
blocked. Saves and even SoTA rate that game as ordinary. Total shots faced sees it for what
it was:

| Cape Verde vs | saves | shots on target faced | **total shots faced** |
|---|---|---|---|
| Spain | 7 | 7 | **27** |
| Uruguay | 0 | 2 | **17** |
| Argentina (R32) | 8 | 11 | **22** |

**Caveat, stated up front:** small samples, an effect that is directional but not firmly
significant, and comparing real tournaments confounds expansion with era/tactics — which is
exactly what Part 2 below disentangles. Sanity check: the pipeline recovers Vozinha's 7 saves vs Spain and Al-Owais'
9 vs Uruguay from the raw data.

---

## Part 2 — Isolating expansion (`model.py`)

The comparison above mixes two things: the field grew (32→48) **and** it's a later era.
To separate them we (1) rate each team from real goals, (2) fit one "pressure law" —
*bigger strength gap ⇒ more shots on the weaker keeper* — (3) **validate** it against the
real 2026 distribution, then (4) run a 32-team and a 48-team field through the **same** law,
changing only how spread-out the teams are.

**The law holds:** `E[besieged shots-on-target] = exp(1.56 + 0.11·|gap|)` — the positive
slope is the mechanism, confirmed in real data.

**It's validated, not assumed:** fed 2026's real matchups it predicts P(≥8 SoT) = 0.22
(95% CI 0.14–0.32) vs 0.25 actual; distributions agree (KS p ≈ 1.0). Unlike the original
toy sim, this model is checked against the tournament that happened.

**Expansion, with football held constant:**

| | 32-team field | 48-team field |
|---|---|---|
| Spread of team strengths (std) | 0.84 | 1.17 |
| Sieges per tournament | ~8.1 | ~14.5 |
| Per-game siege probability | 17.0% | 20.1% |

- **Per tournament: ~1.8×** more sieges — but **1.5× of that is just more games** (72 vs 48).
- **Per game: ~1.18×.** Holding football constant, a wider field makes each game only ~18%
  more likely to become a siege.

**Why this matters:** the original viral post claimed sieges "roughly tripled" (~3×) and
each game was "more than twice as likely" (>2×). The validated model says **1.8× total and
1.18× per game.** And since the *uncontrolled* real per-game jump was ~2×, expansion explains
only a modest slice of it — **most of the rest is era/tactics**, the confounder the first
version ignored. Expansion buries more keepers mainly by adding games, not by making each
game dramatically more one-sided.

Run it: `python -m wc_siege.model`

---

## The flow (five small steps)

Each step is one small, commented module in `wc_siege/`. Read them in order.

| Step | File | What it does |
|------|------|--------------|
| 1 | `collect.py` | Pull goalkeeper match logs from FBref (2018/2022/2026) → `data/raw/` |
| 2 | `clean.py` | Reshape into one tidy row per team-per-game → `data/processed/team_games.csv` |
| 3 | `analyze.py` | Per-game siege distributions, expansion decomposition, significance test |
| 4 | `model.py` | *(Part 2)* fit + **validate** an expansion model against the real data |
| 5 | `viz.py` | The charts for Reddit / LinkedIn → `figures/` |

`run.py` chains them together.

---

## Run it

### See the whole pipeline right now (no internet, fake data)

```bash
pip install -r requirements.txt
python run.py --demo
```

This generates clearly-labelled **synthetic** data and runs steps 2–5 so you can
watch the flow. Every synthetic output is stamped `SAMPLE` / `NOT REAL`.

### Run it for real

FBref blocks cloud/datacenter IPs, so **run the collector on your own machine:**

```bash
python -m wc_siege.collect        # writes data/raw/2018.csv, 2022.csv, 2026.csv
python run.py                     # clean → analyze → viz on the REAL data
```

The raw pulls are committed to `data/raw/`, so once they exist, anyone can rerun
the analysis without touching FBref again. That is what makes this reproducible.

---

## What the numbers mean

- **Per-game siege probability** — the fraction of group-stage games where the
  besieged keeper hit a threshold. This strips out "2026 just has more games."
- **Expansion decomposition** — splits the rise in siege *count* into the part
  explained by more matches vs. the part explained by games being more lopsided.
  (This is the exact claim the original post asserted; here it's measured.)
- **Distribution test** — Mann-Whitney (is 2026 shifted higher?) and KS (do the
  distributions differ in shape?), because save counts are skewed integer data.

---

## Knockouts — expansion's second siege mechanism

The original post *asserted* "knockouts pit similar teams, so they add almost no sieges."
That was refuted on Reddit (Cape Verde–Argentina, Paraguay–Germany, England–DR Congo) and
OP conceded it. So we measure it instead of assuming it — and it matters, because the
48-team format adds a **Round of 32 that the 32-team format never had** (it went
group → Round of 16).

| 2026 knockout round | games | P(besieged keeper faces ≥8 shots on target) |
|---|---|---|
| **Round of 32** *(new in 48-team format)* | 16 | **0.25** — same as the group stage |
| Round of 16 | 8 | 0.00 |
| Quarter-finals | 4 | 0.50 |

The Round of 32 is **not** evenly matched — it keeps weaker teams alive one round longer
(Vozinha's Cape Verde faced 11 shots on target vs Argentina here). At P≈0.25 over 16 games
it adds **~4 siege games** that couldn't exist under the old format. So excluding knockouts
*understated* expansion's effect. (Caveat: some knockout games go to extra time, which
inflates shot counts a little; even so, the Round of 32 clearly out-sieges the Round of 16.)

## Honesty notes

- **Group stage vs knockouts, kept separate.** The headline comparison is group-stage only
  (everyone plays 3 games — a clean, symmetric comparison). Knockouts are analysed on their
  own above, because sample sizes are tiny and extra time distorts counts.
- **2018 + 2022 as the 32-team baseline.** Comparing real tournaments means tactics/era are a
  confounder; we say so rather than pretend a simulation removes it. Part 2's model isolates
  the pure expansion effect.
- **Saves ≠ siege.** We carry three measures — saves, shots-on-target-against, and total
  shots faced — and report all three rather than the flattering one. Total shots is what
  catches an off-target/blocked battering like Spain 0–0 Cape Verde.
- **No xG.** FBref's team match-log shooting table exposes only the "Standard" block
  (Gls/Sh/SoT/PK), with no `xG` column, so expected-goals-against isn't available by this
  route. Total shots faced is the closest available proxy; xG would need a different
  source or the per-match report pages.
- **Multiple comparisons.** Three correlated measures are tested, so a nominal p<0.05 is
  reported against a Bonferroni bar (0.017) rather than declared a win.

Data: FBref (StatsBomb). Tools: Python, pandas, NumPy, SciPy, Matplotlib.

## License

MIT
