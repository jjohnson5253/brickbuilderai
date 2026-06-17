"""Build a DPO preference dataset from per-sample Chamfer distance scores.

Given a JSON file mapping ``prompt_id -> {sample_id: chamfer_distance}``, produce a
list of preference pairs ``{"prompt_id", "chosen", "rejected"}`` where the chosen
sample has a strictly lower Chamfer distance than the rejected one, and the two are
within a configurable relative gap (default 20%) to avoid degenerate easy pairs.
"""

import argparse
import json
from itertools import combinations


def build_pairs(cd_scores: dict, max_relative_gap: float = 0.2):
    dataset = []
    for prompt_id, samples in cd_scores.items():
        if len(samples) < 2:
            continue
        for k1, k2 in combinations(samples.keys(), 2):
            v1, v2 = samples[k1], samples[k2]
            if v1 == v2:
                continue
            if v1 > v2:
                k1, k2, v1, v2 = k2, k1, v2, v1
            if v1 > 0 and (v2 - v1) / v1 <= max_relative_gap:
                dataset.append({"prompt_id": prompt_id, "chosen": k1, "rejected": k2})
    return dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cd_file", required=True, help="Input JSON: prompt_id -> {sample_id: cd}")
    parser.add_argument("--output", required=True, help="Output JSON with preference pairs")
    parser.add_argument("--max_relative_gap", type=float, default=0.2)
    args = parser.parse_args()

    with open(args.cd_file, "r") as f:
        cd_scores = json.load(f)

    dataset = build_pairs(cd_scores, max_relative_gap=args.max_relative_gap)
    print(f"Built {len(dataset)} preference pairs")

    with open(args.output, "w") as f:
        json.dump(dataset, f, indent=4)


if __name__ == "__main__":
    main()
