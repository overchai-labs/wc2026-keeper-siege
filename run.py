"""
run.py -- the whole pipeline in order, so you (and any reviewer) can see the flow.

    python run.py --demo    # run on SYNTHETIC sample data (no internet needed)
    python run.py           # run on REAL data (requires data/raw from the collector)

Steps, in order:
    1. collect  (only for real data; must run on your home machine -- see collect.py)
    2. clean    -> data/processed/team_games.csv
    3. analyze  -> prints the report
    4. viz      -> figures/*.png

--demo skips 1-2 and generates synthetic processed data instead, so the analysis
and charts run end-to-end today. Every synthetic output is clearly labelled.
"""
import argparse
import sys

# Make `src/` importable when running as a plain script.
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent / "src"))

from wc_siege import analyze, viz  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the keeper-siege pipeline.")
    parser.add_argument("--demo", action="store_true", help="Use synthetic sample data.")
    args = parser.parse_args()

    if args.demo:
        from wc_siege import sample_data
        print("=== Step 0: generate SYNTHETIC sample data (demo mode) ===")
        sample_data.generate()
    else:
        from wc_siege import clean
        print("=== Step 2: clean real raw data -> tidy table ===")
        clean.clean()

    print("\n=== Step 3: analyze ===")
    analyze.main()

    print("\n=== Step 5: visualise ===")
    viz.make_figure("max_saves")
    viz.make_figure("max_sota")
    print("\nDone. See figures/ for the charts.")


if __name__ == "__main__":
    main()
