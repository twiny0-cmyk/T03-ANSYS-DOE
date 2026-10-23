"""Fail-closed convergence evaluator. No ANSYS imports, no synthetic solver data."""
import math
import re

LIMITS = {'continuity':1e-4,'x-velocity':1e-5,'y-velocity':1e-5,'z-velocity':1e-5,'k':1e-4,'omega':1e-4}
OUTLETS = ['outlet_'+str(i) for i in range(1,6)]


def finite(value):
    return isinstance(value,(float,int)) and not isinstance(value,bool) and math.isfinite(value)


def parse_residual_xy(text):
    series={}
    active=None
    for line in text.splitlines():
        label=re.search(r'xy/key/label\s+"([^"]+)"',line)
        if label:
            active=label.group(1)
            if active in series: raise ValueError('Duplicate residual curve')
            series[active]=[]
        elif active:
            if line.strip()==')': active=None; continue
            parts=line.split()
            if len(parts)==2:
                try: x,y=map(float,parts)
                except ValueError: continue
                if not finite(x) or not finite(y) or y<0 or int(x)!=x: raise ValueError('Invalid residual point')
                series[active].append((int(x),y))
    if not set(LIMITS)<=set(series): raise ValueError('Missing required residual history')
    return series


def evaluate(history, at600, at700):
    last={}
    for name,limit in LIMITS.items():
        points=history[name]
        if len(points)<20 or [p[0] for p in points[-20:]]!=list(range(681,701)):
            raise ValueError('Require iterations 681..700 for every residual')
        if len({p[0] for p in points})!=len(points): raise ValueError('Duplicate residual iteration')
        if any(not finite(p[1]) or p[1]<0 for p in points): raise ValueError('Invalid residual')
        last[name]=max(p[1] for p in points[-20:])
    for flows in [at600,at700]:
        if set(flows)!=set(['inlet']+OUTLETS) or any(not finite(v) for v in flows.values()): raise ValueError('Invalid flux sample')
        if flows['inlet']<=0 or any(flows[n]>=0 for n in OUTLETS): raise ValueError('Unexpected signed flux or reverse flow')
    delta={n:100*abs(at700[n]-at600[n])/abs(at700[n]) for n in OUTLETS}
    total=-sum(at700[n] for n in OUTLETS)
    imbalance=100*abs(at700['inlet']-total)/at700['inlet']
    residual_pass=all(last[n]<=v for n,v in LIMITS.items())
    return dict(pass_convergence=residual_pass and max(delta.values())<0.1 and imbalance<0.1,
                residual_max_last20=last,residual_limits=LIMITS,residual_pass=residual_pass,
                outlet_change_percent=delta,flow_stability_pass=max(delta.values())<0.1,
                mass_imbalance_percent=imbalance,mass_balance_pass=imbalance<0.1,
                strict_solver_target_pass=all(last[n]<=1e-5 for n in LIMITS))
