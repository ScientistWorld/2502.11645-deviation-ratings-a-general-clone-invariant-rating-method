#!/usr/bin/env python3
"""Lossless metric comparison for the shortcut audit; no invented rank score."""
import json
import math
from pathlib import Path

ROOT = Path('/home/user/redteam')


def flatten(scores):
    return {experiment + '/' + method + '/' + metric: value
            for experiment, entry in scores['experiments'].items()
            for method, metrics in entry['results'].items()
            for metric, value in metrics.items()}


def main():
    seeds = [flatten(json.loads((ROOT / f'reference_seeds/seed_{s}/scores_test.json').read_text()))
             for s in (0, 1, 2)]
    spread = {key: {'min': min(row[key] for row in seeds),
                    'max': max(row[key] for row in seeds),
                    'spread': max(row[key] for row in seeds) - min(row[key] for row in seeds)}
              for key in seeds[0]}
    (ROOT / 'reference_seed_spread.json').write_text(json.dumps(spread, indent=2))
    comparisons = {}
    for shortcut in json.loads((ROOT / 'shortcut_cases.json').read_text()):
        folder = ROOT / shortcut
        status = json.loads((folder / 'status.json').read_text())
        row = {'test_exit_code': status.get('test', {}).get('exit_code'),
               'train_exit_code': status.get('train', {}).get('exit_code'),
               'nonfinite_test_fields': status.get('nonfinite_test_fields', [])}
        if (folder / 'scores_test.json').exists():
            values = flatten(json.loads((folder / 'scores_test.json').read_text()))
            row['test_metrics'] = values
            row['changed_vs_reference'] = {key: {'reference': seeds[0].get(key), 'shortcut': val}
                                           for key, val in values.items()
                                           if key not in seeds[0] or val != seeds[0][key]}
            row['missing_vs_reference'] = sorted(set(seeds[0]) - set(values))
        comparisons[shortcut] = row
    (ROOT / 'shortcut_comparisons.json').write_text(json.dumps(comparisons, indent=2))
    print(json.dumps({key: {'test': val['test_exit_code'],
                            'changed': len(val.get('changed_vs_reference', {})),
                            'nonfinite': len(val['nonfinite_test_fields'])}
                      for key, val in comparisons.items()}, indent=2))


if __name__ == '__main__':
    main()
