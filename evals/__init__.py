"""evals — offline measurement of what the assistant actually does.

The README says what J.A.R.V.I.S can do. This checks whether it does.

    python -m evals.runner
    python -m evals.runner --report

Nothing here touches the network, the microphone, or a real window, so it runs
on a laptop in a few seconds. An eval that is slow or flaky gets skipped, and a
skipped eval is indistinguishable from a passing one.
"""