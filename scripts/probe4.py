import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

for name in ["C8v6", "A7v16", "F#7v1", "C7v6"]:
    a = json.load(open(os.path.join(os.path.dirname(__file__), "..", "reference", "analysis", f"{name}.json")))
    print(f"{name}: f0={a['f0']:.1f} B={a['B']:.2e} npart={a['n_partials']} "
          f"rel={a.get('release_s')} dur={a['duration']:.1f} peak={a['peak_abs']:.3f}")
    for p in a["partials"]:
        has = "a_fast" in p
        if has:
            print(f"   n{p['n']} f={p['freq']:.0f} amp={20*math.log10(p['amp']+1e-12):6.1f}dB "
                  f"a1={20*math.log10(p['a_fast']*a['peak_abs']+1e-12):6.1f}dB t1={p['tau_fast']:.2f} "
                  f"a2={20*math.log10(p['a_slow']*a['peak_abs']+1e-12):6.1f}dB t2={p['tau_slow']:.2f}")
        else:
            print(f"   n{p['n']} f={p['freq']:.0f} amp={20*math.log10(p['amp']+1e-12):6.1f}dB  (no decay fit)")
    print("   thump:", a["thump_db"])
    print("   bed:  ", a["bed_db"])
    print("   t60:  ", a["bed_t60"])
