#!/usr/bin/env python3
"""
alt_generate_json.py
--------------------
Generate ~N MB of synthetic e-commerce transactions as JSON files (arrays).

- Writes shard files: sample_part_<i>.json
- Each file is a compact JSON array: [ {...}, {...}, ... ]
- Size-driven: fills each shard up to its byte budget (approx)
- Tunable ratios of invalid/large/normal records
- Optional padding per record to reach size targets faster

Examples:
  python alt_generate_json.py
  python alt_generate_json.py --target-mb 2 --shards 8
  python alt_generate_json.py --target-mb 5 --shards 4 --invalid-ratio 0.02 --large-ratio 0.03
"""

import argparse
import json
import random
import string
import time
import uuid
from pathlib import Path
from typing import Dict, Tuple

DEFAULT_TARGET_MB = 2
DEFAULT_SHARDS = 8

def rand_str(n: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=n))

def make_invalid(pad_kb: int = 0) -> Dict:
    rec = {
        "transaction_id": str(uuid.uuid4()),
        "customer_id": rand_str(8),
        "amount": 0.0,  # invalid by design
        "items": [{"product_id": rand_str(6), "quantity": 1, "price": 0.0}],
    }
    if pad_kb > 0:
        rec["_pad"] = "x" * (pad_kb * 1024)
    return rec

def make_large(threshold: float, pad_kb: int = 0) -> Dict:
    rec = {
        "transaction_id": str(uuid.uuid4()),
        "customer_id": rand_str(8),
        "amount": round(random.uniform(threshold + 0.01, threshold * 2.0), 2),
        "items": [{
            "product_id": rand_str(6),
            "quantity": random.randint(1, 3),
            "price": round(random.uniform(10, 200), 2),
        }],
    }
    if pad_kb > 0:
        rec["_pad"] = "x" * (pad_kb * 1024)
    return rec

def make_normal(threshold: float, pad_kb: int = 0) -> Dict:
    floor = max(1.0, threshold * 0.01)
    rec = {
        "transaction_id": str(uuid.uuid4()),
        "customer_id": rand_str(8),
        "amount": round(random.uniform(floor, threshold), 2),
        "items": [{
            "product_id": rand_str(6),
            "quantity": random.randint(1, 3),
            "price": round(random.uniform(10, 200), 2),
        }],
    }
    if pad_kb > 0:
        rec["_pad"] = "x" * (pad_kb * 1024)
    return rec

def choose_kind(invalid_ratio: float, large_ratio: float) -> str:
    r = random.random()
    if r < invalid_ratio:
        return "invalid"
    if r < invalid_ratio + large_ratio:
        return "large"
    return "normal"

def generate_shard(
    shard_idx: int,
    bytes_budget: int,
    out_dir: Path,
    invalid_ratio: float,
    large_ratio: float,
    large_threshold: float,
    pad_kb: int,
) -> Tuple[int, int, int, int, int]:
    """
    Build a Python list of records while tracking encoded byte size you'll write as JSON.
    Returns: (num_invalid, num_large, num_normal, records_count, bytes_written_estimate)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"sample_part_{shard_idx}.json"

    records = []
    n_invalid = n_large = n_normal = 0
    # Start with 2 bytes for "[]"
    written = 2
    # For commas between elements, we add 1 byte per additional element.

    t0 = time.time()
    while True:
        kind = choose_kind(invalid_ratio, large_ratio)
        if kind == "invalid":
            rec = make_invalid(pad_kb)
        elif kind == "large":
            rec = make_large(large_threshold, pad_kb)
        else:
            rec = make_normal(large_threshold, pad_kb)

        # Compute cost if we add this record (compact separators like final dump)
        rec_json = json.dumps(rec, separators=(",", ":"))
        add_cost = len(rec_json.encode("utf-8")) + (1 if records else 0)  # + comma if not first

        if written + add_cost > bytes_budget and records:
            # stop if we already have at least one record
            break

        # Otherwise include it
        records.append(rec)
        written += add_cost

        if kind == "invalid":
            n_invalid += 1
        elif kind == "large":
            n_large += 1
        else:
            n_normal += 1

        # If single record would exceed budget (tiny budget case), still allow 1
        if written >= bytes_budget and len(records) > 0:
            break

    # Write the JSON array compactly
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, separators=(",", ":"))
        f.write("\n")

    dt = time.time() - t0
    print(f"✅ Shard {shard_idx}: {len(records)} records, ~{written/1024:.1f} KB in {dt:.2f}s "
          f"(invalid={n_invalid}, large={n_large}, normal={n_normal}) → {out_path.name}")
    return n_invalid, n_large, n_normal, len(records), written

def main():
    p = argparse.ArgumentParser(description="Generate ~N MB of JSON (array) e-commerce records.")
    p.add_argument("--target-mb", type=float, default=DEFAULT_TARGET_MB,
                   help="Approx total size to generate (MB). Default: 2")
    p.add_argument("--shards", type=int, default=DEFAULT_SHARDS,
                   help="Number of JSON files to write. Default: 8")
    p.add_argument("--invalid-ratio", type=float, default=0.01,
                   help="Fraction of invalid records. Default: 0.01")
    p.add_argument("--large-ratio", type=float, default=0.02,
                   help="Fraction of large-amount records. Default: 0.02")
    p.add_argument("--large-threshold", type=float, default=10_000.0,
                   help="Amount above which a record is 'large'. Default: 10000")
    p.add_argument("--pad-kb", type=int, default=0,
                   help="Optional padding per record (KB). Default: 0")
    p.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    p.add_argument("--out-dir", type=Path, default=Path("."), help="Output directory. Default: current dir")
    args = p.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    target_bytes = int(args.target_mb * 1024 * 1024)
    shards = max(1, args.shards)
    per_shard = target_bytes // shards
    remainder = target_bytes % shards

    print(f"\n Target ~{args.target_mb} MB across {shards} shard(s)"
          f"  (≈{per_shard/1024:.1f} KB each, +{remainder} remainder bytes)")
    print(f"   Ratios: invalid={args.invalid_ratio:.3f}, large={args.large_ratio:.3f}")
    print(f"   Large threshold: {args.large_threshold}, Padding: {args.pad_kb} KB/record\n")

    tot_invalid = tot_large = tot_normal = tot_recs = tot_bytes = 0
    t0 = time.time()

    for i in range(shards):
        budget = per_shard + (remainder if i == shards - 1 else 0)
        inv, lg, norm, recs, wrote = generate_shard(
            shard_idx=i,
            bytes_budget=budget,
            out_dir=args.out_dir,
            invalid_ratio=args.invalid_ratio,
            large_ratio=args.large_ratio,
            large_threshold=args.large_threshold,
            pad_kb=args.pad_kb,
        )
        tot_invalid += inv
        tot_large += lg
        tot_normal += norm
        tot_recs += recs
        tot_bytes += wrote

    dt = time.time() - t0
    mb = tot_bytes / (1024 * 1024)
    print("\n================ SUMMARY ================")
    print(f"✅ Total records  : {tot_recs}")
    print(f"📦 Approx size    : {mb:.2f} MB (target {args.target_mb} MB)")
    print(f"🔎 Counts         : invalid={tot_invalid}, large={tot_large}, normal={tot_normal}")
    print(f"⏱️ Time           : {dt:.2f} seconds")
    print("=========================================\n")

if __name__ == "__main__":
    main()
