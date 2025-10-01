import json, os, sys, time
from datetime import datetime
import boto3
from botocore.config import Config

CURRENCY    = os.getenv("CURRENCY", "USD")
GRANULARITY = os.getenv("GRANULARITY", "MONTHLY").upper()
GROUP_BY    = [g.strip().upper() for g in os.getenv("GROUP_BY", "").split(",") if g.strip()]
METRIC      = os.getenv("METRIC", "UnblendedCost")

VALID_GROUP_BY = {
    "AZ","INSTANCE_TYPE","LINKED_ACCOUNT","OPERATION","PURCHASE_TYPE","SERVICE",
    "USAGE_TYPE","PLATFORM","TENANCY","RECORD_TYPE","LEGAL_ENTITY_NAME",
    "INVOICING_ENTITY","DEPLOYMENT_OPTION","DATABASE_ENGINE","CACHE_ENGINE",
    "INSTANCE_TYPE_FAMILY","REGION","BILLING_ENTITY","RESERVATION_ID",
    "SAVINGS_PLANS_TYPE","SAVINGS_PLAN_ARN","OPERATING_SYSTEM","PAYER_ACCOUNT"
}

def _validate_group_by(glist):
    invalid = [g for g in glist if g not in VALID_GROUP_BY]
    if invalid:
        raise ValueError(
            f"Invalid GROUP_BY values: {', '.join(invalid)}. "
            f"Valid: {', '.join(sorted(VALID_GROUP_BY))}"
        )

ce = boto3.client("ce", config=Config(retries={"max_attempts": 10, "mode": "standard"}))

def read_msg():
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)

def write_msg(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

def normalize_date(s: str) -> str:
    datetime.strptime(s, "%Y-%m-%d")
    return s

def _metric_amount_total(total: dict, metric_key: str) -> float:
    try:
        return float(total.get(metric_key, {}).get("Amount", "0") or 0)
    except Exception:
        return 0.0

def _metric_amount_group(metrics: dict, metric_key: str) -> float:
    try:
        return float(metrics.get(metric_key, {}).get("Amount", "0") or 0)
    except Exception:
        return 0.0

def get_cost_and_usage(start: str, end: str, granularity: str, group_by_dims: list[str]):
    start = normalize_date(start); end = normalize_date(end)
    _validate_group_by(group_by_dims)

    dims = [{"Type": "DIMENSION", "Key": d} for d in group_by_dims if d]
    kwargs = {
        "TimePeriod": {"Start": start, "End": end},
        "Granularity": granularity,
        "Metrics": [METRIC],
        "GroupBy": dims[:2] if dims else []
    }

    results, token = [], None
    while True:
        if token:
            kwargs["NextPageToken"] = token
        resp = ce.get_cost_and_usage(**kwargs)
        results.extend(resp.get("ResultsByTime", []))
        token = resp.get("NextPageToken")
        if not token:
            break

    total_sum = 0.0
    timeline = []
    grouped_totals = {}

    for bucket in results:
        btotal = bucket.get("Total", {})
        period_amt = _metric_amount_total(btotal, METRIC)

        if period_amt == 0.0 and bucket.get("Groups"):
            for g in bucket["Groups"]:
                period_amt += _metric_amount_group(g.get("Metrics", {}), METRIC)

        unit = (btotal.get(METRIC, {}) or {}).get("Unit", CURRENCY)
        timeline.append({
            "start": bucket["TimePeriod"]["Start"],
            "end": bucket["TimePeriod"]["End"],
            "total": round(period_amt, 2),
            "unit": unit or CURRENCY
        })
        total_sum += period_amt

        for g in bucket.get("Groups", []):
            keys = tuple(g.get("Keys", []))
            gamt = _metric_amount_group(g.get("Metrics", {}), METRIC)
            grouped_totals[keys] = grouped_totals.get(keys, 0.0) + gamt

    grouped = []
    for keys, amt in grouped_totals.items():
        entry = {"amount": round(amt, 2), "unit": CURRENCY}
        for i, k in enumerate(keys):
            dim_name = group_by_dims[i] if i < len(group_by_dims) else f"DIM{i+1}"
            entry[dim_name.lower()] = k
        grouped.append(entry)
    grouped.sort(key=lambda x: x["amount"], reverse=True)

    return {
        "currency": CURRENCY,
        "granularity": granularity,
        "metric": METRIC,
        "period": {"start": start, "end": end},
        "total": round(total_sum, 2),
        "timeline": timeline,
        "grouped": grouped[:50]
    }

def get_cost_forecast(start: str, end: str, metric=None):
    metric = metric or ("UNBLENDED_COST" if METRIC.lower() == "unblendedcost" else "AMORTIZED_COST")
    start = normalize_date(start); end = normalize_date(end)
    resp = ce.get_cost_forecast(
        TimePeriod={"Start": start, "End": end},
        Metric=metric,
        Granularity="MONTHLY",
        PredictionIntervalLevel=95
    )
    items = []
    tot_mean = tot_lo = tot_hi = 0.0
    for r in resp.get("ForecastResultsByTime", []):
        mean = float(r["MeanValue"]); lo = float(r["PredictionIntervalLowerBound"]); hi = float(r["PredictionIntervalUpperBound"])
        items.append({
            "start": r["TimePeriod"]["Start"],
            "end": r["TimePeriod"]["End"],
            "mean": round(mean, 2),
            "lower": round(lo, 2),
            "upper": round(hi, 2),
            "unit": CURRENCY
        })
        tot_mean += mean; tot_lo += lo; tot_hi += hi

    return {
        "currency": CURRENCY,
        "metric": metric,
        "period": {"start": start, "end": end},
        "forecast": items,
        "aggregate": {
            "mean": round(tot_mean, 2),
            "lower": round(tot_lo, 2),
            "upper": round(hi, 2) if (hi:=tot_hi) else round(tot_hi, 2),
            "unit": CURRENCY
        }
    }

def handle_tool_call(msg):
    name = msg.get("name"); params = msg.get("params", {})
    try:
        if name == "get_cost_summary":
            start = params.get("start"); end = params.get("end")
            if not start or not end:
                return {"type": "error", "message": "start and end are required (YYYY-MM-DD)"}
            data = get_cost_and_usage(start, end, GRANULARITY, GROUP_BY)
            return {"type": "tool_result", "id": msg.get("id"), "content": data}
        if name == "get_cost_forecast":
            start = params.get("start"); end = params.get("end")
            if not start or not end:
                return {"type": "error", "message": "start and end are required (YYYY-MM-DD)"}
            data = get_cost_forecast(start, end)
            return {"type": "tool_result", "id": msg.get("id"), "content": data}
        return {"type": "error", "message": f"unknown tool: {name}"}
    except ce.exceptions.DataUnavailableException as e:
        print(f"[CE] DataUnavailable: {e}", file=sys.stderr)
        return {"type": "error", "message": "Cost data unavailable for the requested range", "details": str(e)}
    except Exception as e:
        print(f"[CE] General error: {e}", file=sys.stderr)
        return {"type": "error", "message": "Failed to call Cost Explorer", "details": str(e)}

def main():
    write_msg({"type": "hello", "server": "aws-cost-insights"})
    for _ in range(10000):
        msg = read_msg()
        if not msg:
            break
        if msg.get("type") == "tool_call":
            write_msg(handle_tool_call(msg))
        elif msg.get("type") == "ping":
            write_msg({"type": "pong", "ts": time.time()})
        else:
            write_msg({"type": "error", "message": "unknown message", "echo": msg})
    sys.exit(0)

if __name__ == "__main__":
    main()
