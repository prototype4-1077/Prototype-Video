"""World-space blocking for June's continuous 24-second movement audition.

Pure Python: independent of Blender, camera, render quality, and accepted plates.
Units are the inherited v8 rig's scene units. This is a development audition,
not a promoted episode or an assertion of production art quality.
"""
from __future__ import annotations
import math

FPS = 30
FRAMES = 720
STEP_WINDOWS = ((151, 195, 'L', -.98), (211, 255, 'R', -1.36),
                (271, 315, 'L', -1.74), (331, 375, 'R', -1.74))
BEATS = ((1, 45, 'notice'), (46, 135, 'stand'), (136, 150, 'balance'),
         (151, 390, 'walk'), (391, 450, 'reach'), (451, 510, 'lift'),
         (511, 600, 'address'), (601, 645, 'chuckle'), (646, 720, 'settle'))


def ease(t):
    t = max(0., min(1., t))
    return t*t*t*(t*(t*6-15)+10)


def blend(a, b, t):
    return tuple(x+(y-x)*ease(t) for x, y in zip(a,b))


def track(frame, keys):
    if frame <= keys[0][0]: return keys[0][1]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if frame <= b: return blend(x,y,(frame-a)/(b-a))
    return keys[-1][1]


def foot(frame, side):
    y = -.60
    for start,end,which,dest in STEP_WINDOWS:
        if side != which: continue
        if frame >= end: y = dest
        elif frame > start:
            u=(frame-start)/(end-start)
            # C2 lift, zero velocity/acceleration at contact.
            return ((-.22 if side=='L' else .22), y+(dest-y)*ease(u),
                    .34 + .12*64*u**3*(1-u)**3), False
        else: break
    return ((-.22 if side=='L' else .22), y, .34), True


def sample(frame):
    if not isinstance(frame,int) or not 1 <= frame <= FRAMES:
        raise ValueError('frame must be an integer in 1..720')
    body = track(frame,[(1,(0.,0.,0.)),(45,(0.,-.10,-.025)),
        (95,(0.,-.36,.14)),(135,(0.,-.43,.30)),
        (150,(.035,-.43,.30)),(195,(-.035,-.64,.30)),
        (210,(-.035,-.68,.30)),(255,(.035,-1.02,.30)),
        (270,(.035,-1.06,.30)),(315,(-.035,-1.39,.30)),
        (330,(-.035,-1.42,.30)),(375,(0.,-1.57,.30)),
        (390,(0.,-1.57,.30)),(450,(.045,-1.60,.28)),
        (510,(0.,-1.57,.30)),(720,(0.,-1.57,.30))])
    feet={s:foot(frame,s) for s in ('L','R')}
    hand_r=track(frame,[(1,(.62,-.43,1.48)),(135,(.52,-.67,1.69)),
       (150,(.52,-.67,1.69)),(195,(.52,-.90,1.69)),
       (255,(.52,-1.18,1.69)),(315,(.52,-1.55,1.69)),
       (390,(.52,-1.75,1.69)),(450,(.60,-1.87,1.72)),
       (465,(.60,-1.87,1.72)),(510,(.45,-1.97,1.95)),
       (600,(.45,-1.97,1.95)),(645,(.45,-1.97,1.95)),
       (720,(.45,-1.97,1.95))])
    hand_l=track(frame,[(1,(-.58,.05,1.48)),(60,(-.58,.05,1.48)),
        (135,(-.52,-.67,1.69)),(150,(-.52,-.67,1.69)),
        (195,(-.52,-.91,1.69)),(255,(-.52,-1.20,1.69)),
        (315,(-.52,-1.55,1.69)),(390,(-.52,-1.75,1.69)),
        (510,(-.52,-1.75,1.69)),(550,(-.56,-1.96,1.90)),
        (590,(-.52,-1.83,1.77)),(645,(-.52,-1.75,1.69)),
        (720,(-.52,-1.75,1.69))])
    return {'frame':frame,'beat':next(n for a,b,n in BEATS if a<=frame<=b),
            'pelvis_offset':body,'feet':feet,'hand.L':hand_l,'hand.R':hand_r,
            'grip':ease((frame-435)/25), 'mug_attached':frame>=465,
            'head_yaw':math.radians(18)*ease((frame-500)/45),
            'chuckle':(.008*math.sin((frame-600)*math.pi/9)*math.sin(math.pi*(frame-600)/45)**2
                       if 600<frame<645 else 0.)}


def audit_evaluated(rows, ground):
    """Reject incomplete/nonfinite measured output; never infer an art pass.

Input is Blender's evaluated geometry/bones, not the requested control plan.
Only mechanical measurements belong here. Silhouette, skinning, and acting
acceptance require separately reviewed render evidence.
"""
    if [r['frame'] for r in rows] != list(range(1, FRAMES+1)):
        raise ValueError('expected all 720 evaluated frames in order')
    numbers=[]
    for r in rows:
        for side in ('L','R'):
            foot=r['feet'][side]
            if type(foot['contact']) is not bool:raise ValueError('contact must be boolean')
            numbers.extend(foot['position']);numbers.append(foot['target_error'])
            numbers.append(r['hand_target_error'][side])
            numbers.append(r['sole_min_z']['June_Boot_Sole_'+side])
        numbers.extend(r['mug_position'])
    if not all(math.isfinite(v) for v in numbers):
        raise ValueError('nonfinite evaluated evidence')
    foot_error=max(v['target_error'] for r in rows for v in r['feet'].values())
    hand_error=max(v for r in rows for v in r['hand_target_error'].values())
    slide=max(math.dist(a['feet'][s]['position'],b['feet'][s]['position'])
              for a,b in zip(rows,rows[1:]) for s in ('L','R')
              if a['feet'][s]['contact'] and b['feet'][s]['contact'])
    minimum_sole=min(z-ground for r in rows for z in r['sole_min_z'].values())
    contact_height=max(abs(r['sole_min_z']['June_Boot_Sole_'+s]-ground)
                       for r in rows for s in ('L','R') if r['feet'][s]['contact'])
    attach_step=math.dist(rows[463]['mug_position'],rows[464]['mug_position'])
    collisions=sum(r['boot_table_bbox_collisions'] for r in rows)
    checks={'boot_table_clearance':collisions==0,'foot_target':foot_error<.005,'hand_target':hand_error<.005,
            'planted_ankle_slide':slide<.002,'floor_penetration':minimum_sole>=-.002,
            'planted_sole_height':contact_height<.005,'pickup_continuity':attach_step<.002}
    return {'control_mechanics_passed':all(checks.values()),'checks':checks,
            'max_evaluated_foot_target_error':foot_error,
            'max_evaluated_hand_target_error':hand_error,
            'max_contact_ankle_step':slide,'min_sole_height_above_floor':minimum_sole,
            'max_planted_sole_height_error':contact_height,'mug_attachment_step':attach_step,
            'boot_table_bbox_collisions':collisions,'production_approved':False}
