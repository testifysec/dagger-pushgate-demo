#!/usr/bin/env python3
"""CI minutes and time-to-land per landed change, for three ways of running
checks, with and without a merge queue.

Arms
  A  plain GitHub Actions: setup-go, go test
  B  Dagger on the runner: dagger check on a fresh engine
  C  Dagger + CI/lock + Pushgate: the developer runs dagger check under
     `cilock run`, Pushgate admits the push only with passing evidence, and CI
     verifies that verdict instead of running the suite again

Inputs
  T         suite time on a CI runner, minutes
  k         pushes it takes a change to go green (1 = right first time)
  o_*       fixed overhead per run, minutes (runner start, setup, engine
            boot), measured on GitHub-hosted ubuntu-latest; see bench/RESULTS.md
  price     USD per runner-minute (GitHub-hosted Linux 2-core: 0.006)

Model, per landed change
  A, B without a queue: k PR runs, then one run on main after the merge.
  A, B with a queue:    k PR runs, then one merge-queue run.
  C without a queue:    the k-1 failing attempts are refused at the push and
                        never reach CI; the accepted commit lands on main as
                        pushed, so CI only verifies its verdict, once on the
                        push. Cost: one verify job.
  C with a queue:       one verify job on the PR, then one full merge-queue
                        run, because the merged tree is a new commit.

What the model leaves out, on purpose
  - Arm C moves the suite to the developer's machine. Those minutes are not
    billed, but somebody waits for them; time_to_land counts them.
  - Dagger's warm local cache makes a re-run cheaper than T. The model charges
    the full T every time, which favours A and B.
  - Without a queue, a push that races another one has to rebase, and the new
    commit needs new evidence. rebase_retries() estimates that cost.
"""

import math
import sys

PRICE = 0.006  # USD per minute, GitHub-hosted Linux 2-core


def per_change(arm, mq, T, k, o):
    """Return (billed CI minutes, minutes until the change is on main)."""
    full = {"A": o["A"] + T, "B": o["B"] + T, "C": o["B"] + T}[arm]
    if arm in ("A", "B"):
        billed = k * full + full
        land = k * full + (full if mq else 0)
    elif mq:
        billed = o["V"] + full
        land = k * T + o["V"] + full
    else:
        billed = o["V"]
        land = k * T
    return billed, land


def rebase_retries(T, landings_per_hour):
    """Expected local runs per landed change without a queue, when pushes
    race: another change lands during your T minutes with probability
    1 - exp(-rate*T), and each loss means rebase and run again (geometric)."""
    return math.exp(landings_per_hour / 60.0 * T)


def main():
    o = {"A": float(sys.argv[1]), "B": float(sys.argv[2]), "V": float(sys.argv[3])}
    print("| T (min) | k | arm | queue | CI min | CI $ | to land (min) |")
    print("|---|---|---|---|---|---|---|")
    for T in (2, 5, 10, 20, 30, 60, 100):
        for k in (1, 3):
            for mq in (False, True):
                for arm in "ABC":
                    b, l = per_change(arm, mq, T, k, o)
                    print(f"| {T} | {k} | {arm} | {'yes' if mq else 'no'} | {b:.1f} | {b*PRICE:.3f} | {l:.1f} |")
    print()
    print("Expected local runs per landed change without a queue (arm C), by landings/hour on main:")
    print("| T (min) | 2/h | 6/h | 20/h |")
    print("|---|---|---|---|")
    for T in (2, 5, 10, 20, 30, 60, 100):
        print(f"| {T} | " + " | ".join(f"{rebase_retries(T, r):.2f}" for r in (2, 6, 20)) + " |")


if __name__ == "__main__":
    main()
