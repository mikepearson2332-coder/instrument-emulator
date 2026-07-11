import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

a = json.load(open(os.path.join(os.path.dirname(__file__), "..", "reference", "piano", "analysis", "C4v11.json")))
peak = a["peak_abs"]
print("n | spectral amp dB | a_fast dB | tau_f | a_slow dB | tau_s")
amax = max(p["amp"] for p in a["partials"])
for p in a["partials"]:
    sa = 20 * math.log10(p["amp"] / amax + 1e-12)
    af = 20 * math.log10(p.get("a_fast", 1e-12) + 1e-12)
    as_ = 20 * math.log10(p.get("a_slow", 1e-12) + 1e-12)
    print(f"{p['n']:3d} {p['freq']:8.1f}  {sa:7.1f}  {af:7.1f} {p.get('tau_fast',0):6.2f} {as_:7.1f} {p.get('tau_slow',0):6.2f}")
