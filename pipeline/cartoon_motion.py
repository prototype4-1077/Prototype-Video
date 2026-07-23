"""Per-layer motion curves for limited_2_5d cartoon animation.

Each motion(name) returns a function f(t, dur) -> dict transform:
  dx, dy (px), scale, rotate (deg), opacity (0..1), and optional 'blink' flag
that the renderer applies to a layer. Camera moves live here too. These produce
real subject/prop/environment change, not a single global crop.
"""
from __future__ import annotations
import math

def _sine(t, period, amp, phase=0.0):
    return amp * math.sin(2*math.pi*(t/period) + phase)

def still(t, dur):            return {}
def subtle_breath(t, dur):    return {"dy": _sine(t,3.4,3.0), "scale": 1.0+0.012*math.sin(2*math.pi*t/3.4)}
def sway(t, dur):             return {"dx": _sine(t,4.1,5.0)}
def nod_and_turn(t, dur):     return {"dy": _sine(t,2.6,4.0), "rotate": _sine(t,5.2,2.2), "dx": _sine(t,6.0,3.0)}
def shoulder_shift(t, dur):   return {"dx": _sine(t,5.0,4.0), "dy": _sine(t,3.0,2.0)}
def rock(t, dur):             return {"rotate": _sine(t,2.2,3.5), "dy": _sine(t,2.2,2.0)}
def loop_upward(t, dur):
    p=2.0; ph=(t%p)/p
    return {"dy": -60*ph, "opacity": max(0.0, 0.85*math.sin(math.pi*ph))}
def light_flicker(t, dur):    return {"opacity": 0.82+0.14*abs(math.sin(2*math.pi*t/0.7))}
def passing_shadow(t, dur):   return {"dx": (t/max(dur,0.1))*220-110, "opacity":0.5}
def curtain_move(t, dur):     return {"dx": _sine(t,3.6,6.0), "rotate": _sine(t,3.6,1.5)}
def steam_rise(t, dur):       return loop_upward(t, dur)

def blink_and_glance(t, dur):
    # eyes closed briefly ~ every 2.8s (a real facial change), plus a glance shift
    period=2.8; ph=t%period; blink = ph < 0.16
    return {"dx": _sine(t,5.5,2.5), "blink": blink}

def coffee_gesture(t, dur):
    # arm lifts once mid-clip then settles (ramped)
    c=dur*0.45; w=1.2; x=max(0.0,1-abs(t-c)/w)
    return {"dy": -34*x, "rotate": -10*x, "dx": 6*x}

def arm_gesture(t, dur):      return {"rotate": _sine(t,2.4,7.0), "dy": _sine(t,2.4,4.0)}
def slide_in(t, dur):
    x=min(1.0, t/max(dur*0.5,0.1)); return {"dx": -260*(1-x)}   # cue-token / element enters
def door_open(t, dur):
    x=min(1.0,t/max(dur*0.6,0.1)); return {"rotate": -70*x, "dx": -20*x}
def object_rotate(t, dur):    return {"rotate": (t/max(dur,.1))*90}

REGISTRY = {n:f for n,f in globals().items() if callable(f) and not n.startswith("_")
            and n not in ("math",)}

def camera(name, t, dur):
    """Global camera transform; parallax is applied per-layer by depth in the renderer."""
    if name in (None,"none","static"): return {"scale":1.0,"dx":0.0,"dy":0.0}
    x=t/max(dur,0.1)
    if name=="slow_push":   return {"scale":1.0+0.06*x,"dx":0,"dy":0}
    if name=="slow_pull":   return {"scale":1.06-0.06*x,"dx":0,"dy":0}
    if name=="pan_left":    return {"scale":1.03,"dx": 60*x,"dy":0}
    if name=="pan_right":   return {"scale":1.03,"dx":-60*x,"dy":0}
    if name=="track_to_door": return {"scale":1.02+0.03*x,"dx":-90*x,"dy":0}
    if name=="orbit":       return {"scale":1.03,"dx":40*math.sin(2*math.pi*x),"dy":10*math.cos(2*math.pi*x)}
    return {"scale":1.0,"dx":0,"dy":0}

def get(name):
    return REGISTRY.get(name, still)
