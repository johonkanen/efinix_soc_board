"""Prove the routed-board checks can fail (LPDDR4_IBIS_PLAN.md step 7): deliberately bad versions of real nets, run
through the same routed_si.py chain, eye PNGs to results/eyes/eye_bad_*.png.

  source ../../tools/p2k/bin/kicad_env.sh
  python3 bad_case.py

1. dq1 write, DRAM ODT off (ODT_OFF), max corner, 3200 Mbps: an unterminated line, expect overshoot past VDDQ+0.3 V.
2. dq11 read, FPGA ODT off (lpddr4_odt_off), max corner, 3200 Mbps: unterminated at the FPGA, expect overshoot.
3. dq1 write, typ, 3200 Mbps, every trace forced to 150 ohm and 4x its length (DRAM ODT 60): reflections. Found: the
   eye shrinks to 259 mV but still passes (+53 mV / +48 ps): the ODT absorbs most of it.
4. As 3, with the DRAM ODT off too (mismatched at both ends): expect a closed eye.
"""
import copy, json, os, sys

sys.argv = [sys.argv[0]]
import routed_si as RS          # noqa: E402

R = json.load(open(os.path.join(RS.WORK, 'routes.json')))
CASES = [('bad1_dq1_write_odt_off', R, 'ddr_dq1', 'dq_write', 'max', dict(modt='OFF')),
         ('bad2_dq11_read_fpga_odt_off', R, 'ddr_dq11', 'dq_read', 'max', dict(fodt='off'))]
R3 = copy.deepcopy(R)
for s in R3['ddr_dq1']['segs']: s['mm'] *= 4
CASES.append(('bad3_dq1_write_150ohm_4x', R3, 'ddr_dq1', 'dq_write', 'typ', {}))
CASES.append(('bad4_dq1_write_150ohm_4x_odt_off', R3, 'ddr_dq1', 'dq_write', 'typ', dict(modt='OFF')))

zline = RS.G.zline
for tag, routes, net, kind, corner, st in CASES:
    RS.G.zline = (lambda layer, w: (150.0, zline(layer, w)[1])) if tag.startswith(('bad3', 'bad4')) else zline
    n, meta = RS.build(routes, net, kind, corner, 3200.0, st); n.title = tag
    cache = RS.fastnet.KibisCache(RS.S.KCACHE); cache.resolve(n.ib); n.write(os.path.join(RS.WORK, tag + '.cir'), cache)
    for r in RS.run_job((tag, net, kind, corner, 3200.0, meta, True)):
        if r.get('error'): print(tag, 'ERROR', r['error']); continue
        print(f"{tag}: {r['where']:4} eye {r['eh_mV']:.0f} mV, V margin {r['v_margin_mV']:+.0f} mV, t margin "
              f"{r['t_margin_ps']:+.0f} ps, Vmax/Vmin {r['vmax_mV']:.0f}/{r['vmin_mV']:.0f} mV (limits "
              f"{r['lim_hi_mV']:.0f}/{r['lim_lo_mV']:.0f}: {'ok' if r['limits_ok'] else 'FAIL'}), "
              f"OS/US area {r['os_area_Vns']:.3f}/{r['us_area_Vns']:.3f} V-ns", flush=True)
RS.G.zline = zline
