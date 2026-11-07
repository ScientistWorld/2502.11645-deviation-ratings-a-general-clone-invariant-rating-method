from pathlib import Path
import json
p = Path('/home/user/checkpoints/baseline/uniform_biased_shapley.json')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({'ratings': {'0': {'0': -1e100}}}))
