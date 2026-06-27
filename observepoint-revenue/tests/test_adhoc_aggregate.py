import adhoc_aggregate as agg


ROWS = [
    {"stage": "Commit", "arr": 100}, {"stage": "Commit", "arr": 200},
    {"stage": "Best Case", "arr": 50}, {"stage": "Best Case", "arr": "150"},
]


def test_group_sum_and_count():
    out = {r["stage"]: r for r in agg.aggregate(ROWS, group_keys=("stage",),
                                                sums=("arr",), counts=True)}
    assert out["Commit"]["sum_arr"] == 300.0 and out["Commit"]["count"] == 2
    assert out["Best Case"]["sum_arr"] == 200.0


def test_avg():
    out = {r["stage"]: r for r in agg.aggregate(ROWS, group_keys=("stage",), avgs=("arr",))}
    assert out["Commit"]["avg_arr"] == 150.0


def test_no_group_aggregates_whole_set():
    out = agg.aggregate(ROWS, sums=("arr",), counts=True)
    assert len(out) == 1 and out[0]["sum_arr"] == 500.0 and out[0]["count"] == 4
