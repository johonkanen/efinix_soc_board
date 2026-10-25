"""Hand fixes to check_floorplan's emitted intent: Y701 is an oscillator, not a crystal; the FPGA and LPDDR4 sheets
keep per-part faces (their decaps are pre-flipped to B.Cu by flip_decaps.py)."""
import json, sys
p = sys.argv[1]; d = json.load(open(p))
d['proximity'] = [r for r in d['proximity'] if r.get('ref') != 'Y701' and r.get('near') != 'Y701']
for b in d['blocks']:
    if any(r in b['refs'] for r in ('C509', 'C803')):
        b.pop('side', None)
        d['context']['basis'].pop(f"blocks[{b['name']}].side", None)
json.dump(d, open(p, 'w'), indent=1)
print('fix_intent: done')
