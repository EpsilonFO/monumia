from aids import AIDES
from collections import defaultdict

all_values = defaultdict(set)

for aide in AIDES:
    if "criteres" not in aide:
        continue
    for key, value in aide["criteres"].items():
        if isinstance(value, list):
            for v in value:
                if isinstance(v, (dict, list)):
                    all_values[key].add(str(v))
                else:
                    all_values[key].add(v)
        elif isinstance(value, (dict, list)):
            all_values[key].add(str(value))
        else:
            all_values[key].add(value)

for key in sorted(all_values):
    print(f"\n=== {key} ===")
    for v in sorted(all_values[key], key=str):
        print(f"  - {v}")
