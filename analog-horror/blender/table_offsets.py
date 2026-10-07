"""Turn the contact QA into per-table height offsets (python, no Blender):
python table_offsets.py qa_contacts.json table_offsets.json
Each table is lowered by the 90th-percentile sink of its worst diner (+3 mm), capped at 6 cm."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from layout import OTHER_TABLES, BOOTH_DINERS

qa = json.load(open(sys.argv[1]))
prev = json.load(open(sys.argv[2])) if os.path.exists(sys.argv[2]) else {}
owner = {"man": "couple", "woman": "couple"}
for t in OTHER_TABLES:
    for d in t["diners"]:
        owner[d["tag"]] = t["name"]
for d in BOOTH_DINERS:
    owner[d["tag"]] = "booth" + ("0" if d["tag"].startswith("b0") else "1")
need = {}
for tag, r in qa.items():
    tn = owner.get(tag)
    if tn:
        need[tn] = max(need.get(tn, 0.0), r["sink_p90"])
out = {}
for tn in set(owner.values()):
    extra = need.get(tn, 0.0)
    out[tn] = round(prev.get(tn, 0.0) - min(0.06, extra + (0.003 if extra > 0.002 else 0.0)), 4)
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(json.dumps(out, indent=1))
# knees hitting the underside -> move that diner (and chair) back from the table
dp = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(sys.argv[2]), "diner_offsets.json")
back = json.load(open(dp)) if os.path.exists(dp) else {}
for tag, r in qa.items():
    if r.get("knee_hits_table", 0) > 0.003:
        back[tag] = round(back.get(tag, 0.0) + r["knee_hits_table"] + 0.015, 4)
json.dump(back, open(dp, "w"), indent=1)
print("diner push-back:", back)
# backs pressing through the backrest -> slide only the chair back (the sitter stays on the seat)
cp = os.path.join(os.path.dirname(dp), "chair_offsets.json")
chair = json.load(open(cp)) if os.path.exists(cp) else {}
for tag, r in qa.items():
    if r.get("back_in_chair", 0) > 0.012:
        chair[tag] = round(min(0.09, chair.get(tag, 0.0) + r["back_in_chair"] - 0.006), 4)
json.dump(chair, open(cp, "w"), indent=1)
print("chair slide-back:", chair)
