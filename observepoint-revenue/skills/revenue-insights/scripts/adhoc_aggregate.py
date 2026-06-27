"""Generic group-by aggregation for the ad-hoc fallback — the arithmetic for questions no
vetted recipe covers. The MODEL writes the SQL and passes rows here; this computes. No I/O."""
import currency


def aggregate(rows, group_keys=(), sums=(), counts=False, avgs=()):
    """Group `rows` (list of dicts) by `group_keys`; emit per group: the group key values,
    `sum_<k>` for k in sums, `avg_<k>` for k in avgs, and `count` if counts. With no
    group_keys, aggregates the whole set into one row. Numbers parsed via currency.to_number."""
    groups = {}
    order = []
    for r in rows:
        key = tuple(r.get(k) for k in group_keys)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    out = []
    for key in order:
        g = groups[key]
        rec = {k: v for k, v in zip(group_keys, key)}
        if counts:
            rec["count"] = len(g)
        for k in sums:
            rec[f"sum_{k}"] = sum((currency.to_number(r.get(k)) or 0.0) for r in g)
        for k in avgs:
            vals = [currency.to_number(r.get(k)) for r in g if currency.to_number(r.get(k)) is not None]
            rec[f"avg_{k}"] = (sum(vals) / len(vals)) if vals else None
        out.append(rec)
    return out
