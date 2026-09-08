"""Offline, CC0 anatomical head foundation fitted to June's development rig.

Source provenance and the upstream commit are in the companion asset manifest.
No MakeHuman/MPFB application code is copied or needed at render time.
"""
import gzip
import hashlib
import json
import math
from pathlib import Path


def load():
    path=Path(__file__).resolve().parents[2]/'concept/characters/assets/june_anatomy_cc0.json.gz'
    manifest=json.loads(path.with_name('june_anatomy_cc0_provenance.json').read_text())
    payload=path.read_bytes()
    if hashlib.sha256(payload).hexdigest()!=manifest['derived_sha256']:
        raise ValueError('anatomical source does not match its pinned provenance')
    return json.loads(gzip.decompress(payload))


def fitted_head(bpy, rig, material):
    from pipeline.blender import june_hero_v9 as hero
    from mathutils.bvhtree import BVHTree
    from mathutils import Vector
    data=load();vertices=[]
    for sx,sy,sz in data['head']['vertices']:
        # Eye socket scale is a localized deformation of the connected face.
        sign=1 if sx>=0 else -1;cx=sign*.293125;cz=7.85365
        d=((sx-cx)/.42)**2+((sy-cz)/.30)**2+((sz-1.21)/.40)**2
        weight=math.exp(-d*d)
        sx=cx+(sx-cx)*(1+.48*weight)
        sy=cz+(sy-cz)*(1+.78*weight)
        x=sx*.32+sign*.013*weight;y=-(sz-.40)*.30;z=2.761+(sy-cz)*.32
        # Longer forehead, softer hanging tip and narrow lower jaw.
        if z>2.86:z=2.86+(z-2.86)*.84
        if z<2.761:z=2.761+(z-2.761)*1.40
        if z<2.58:x*=1-.055*hero.smooth((2.58-z)/.22)
        if y<-.20:
            nose=hero.gauss(x,z,0,2.641,.062,.078)
            y-=.036*nose;z-=.018*nose
        if z<2.40:
            t=1-hero.smooth((z-2.26)/.14)
            a=math.atan2(x/.15,-(y-.015)/.22)
            x=hero.blend(x,.105*math.sin(a),t)
            y=hero.blend(y,.015-.110*math.cos(a),t)
            z=max(2.22,z)
        vertices.append((x,y,z))
    faces=[f for f in data['head']['faces'] if any(vertices[i][2]>2.22 for i in f)]
    obj=hero.mesh(bpy,'June_Head',vertices,faces,material,sub=2)
    obj['ce_anatomical_source']='MakeHuman CC0 old male base, locally shaped for June'
    obj['ce_dialogue_ready']=False
    obj.shape_key_add(name='Basis')
    for name in ('smile','thoughtful','soft_chuckle','brow_raise','brow_knit','squint','cheek_raise'):
        key=obj.shape_key_add(name=name)
        for point in key.data:
            x,y,z=point.co
            if y>=0:continue
            if name in ('smile','soft_chuckle','cheek_raise'):
                point.co.z+=.017*hero.gauss(abs(x),z,.095,2.50,.071,.085)
            elif name=='thoughtful':point.co.x+=.004*hero.gauss(x,z,0,2.51,.18,.11)
            elif name=='brow_raise':point.co.z+=.012*hero.gauss(abs(x),z,.107,2.82,.08,.045)
            elif name=='brow_knit':point.co.x-=.05*x*hero.gauss(x,z,0,2.84,.2,.045)
            elif name=='squint':point.co.z+=.006*hero.gauss(abs(x),z,.10,2.72,.08,.022)
    # Sample the subdivided rest surface for fitted age lines and beard follicles.
    bpy.context.view_layer.update()
    ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh()
    bvh=BVHTree.FromPolygons([v.co.copy() for v in m.vertices],[list(p.vertices) for p in m.polygons],all_triangles=False)
    ev.to_mesh_clear()
    hero.base._parent_to_bone(obj,rig,'head')
    def front_y(x,z):
        hit=bvh.ray_cast(Vector((x,-1.,z)),Vector((0,1,0)),2.)
        return hit[0].y if hit[0] is not None else fallback(x,z)
    fallback=hero.face_y
    return obj,front_y,bvh


def groom(bpy, rig, head, mats, bvh):
    """Area-sampled follicles and under-groom patches on the actual head mesh."""
    import bisect
    import random
    from mathutils import Vector
    from pipeline.blender import june_hero_v9 as hero
    rng=random.Random(1907)
    bpy.context.view_layer.update()
    ev=head.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();m.calc_loop_triangles()
    vs=[v.co.copy() for v in m.vertices]
    triangles={key:[] for key in ('scalp','beard','moustache')}
    def region(p):
        x,y,z=p;angle=abs(math.atan2(x,-(y-.035)))
        if (z>2.835 and angle>1.0) or (z>2.72 and angle>1.78) or (z>3.08 and angle>.55):return 'scalp'
        if abs(x)>.225 and 2.56<z<2.81:return None
        if angle<1.45 and z>2.365 and y<-.14:
            if z<2.505 or (abs(x)>.155 and z<2.655):return 'beard'
            if abs(x)<.108 and 2.533<z<2.575 and y>-.37:return 'moustache'
        return None
    for tri in m.loop_triangles:
        ids=list(tri.vertices);a,b,c=(vs[i] for i in ids)
        key=region((a+b+c)/3)
        if key:
            normal=(b-a).cross(c-a);area=normal.length/2
            if area>0:triangles[key].append((ids,area,normal.normalized()))
    ev.to_mesh_clear()
    for category,count in (('scalp',14000),('beard',10000),('moustache',1800)):
        tris=triangles[category]
        if not tris:raise RuntimeError('empty groom region: '+category)
        ids=sorted({i for tri,area,n in tris for i in tri});indices={v:k for k,v in enumerate(ids)}
        pverts=[]
        for i in ids:
            p=vs[i];near,normal,_,_=bvh.find_nearest(p)
            pverts.append(tuple(p+normal*.002))
        under=hero.mesh(bpy,'June_'+category.title()+'_Undergroom',pverts,
                        [tuple(indices[i] for i in f) for f,area,n in tris],mats['hair_base'])
        hero.base._parent_to_bone(under,rig,'head')
        cumulative=[];total=0.
        for f,area,n in tris:total+=area;cumulative.append(total)
        paths=[]
        for i in range(count):
            ids,area,normal=tris[bisect.bisect_left(cumulative,rng.random()*total)]
            a,b,c=(vs[j] for j in ids)
            u=math.sqrt(rng.random());v=rng.random();root=(1-u)*a+u*(1-v)*b+u*v*c
            sign=1 if root.x>=0 else -1
            if category=='scalp':direction=Vector((sign*.15,.75,-.72));length=rng.uniform(.035,.065);lift=.010
            elif category=='beard':direction=Vector((sign*.08,-.02,-1));length=rng.uniform(.019,.035);lift=.006
            else:direction=Vector((sign*.90,-.03,-.5));length=rng.uniform(.024,.045);lift=.007
            tangent=direction-normal*normal.dot(direction)
            if tangent.length<.001:tangent=Vector((1,0,0))
            tangent.normalize();path=[];wave=rng.uniform(-.002,.002)
            for k in range(7):
                t=k/6;p=root+tangent*(t*length)
                near,n,_,_=bvh.find_nearest(p)
                p=near+n*(.002+lift*math.sin(t*math.pi*.9))+Vector((wave*math.sin(t*5),0,0))
                path.append((*p,1-t*.96))
            paths.append(path)
        hero.curves(bpy,'June_'+category.title()+'_Groom',paths,mats['hair'],.00055,rig)


def fitted_hands(bpy, rig, material):
    """Landmark-fit connected hands; retain named proximal/distal digit controls."""
    import numpy as np
    from mathutils import Vector
    from pipeline.blender import june_hero_v9 as hero
    data=load()
    for side,source_name,source_side in (('R','left_hand','l'),('L','right_hand','r')):
        part=data[source_name];joints=data['joints'];anchors=[];targets=[];segments=[]
        wrist=Vector(joints[source_side+'-hand'])
        target_wrist=rig.data.bones['hand.'+side].head_local.copy()
        palm=(Vector(joints[source_side+'-finger-3-1'])+wrist)/2
        target_palm=target_wrist+Vector((0,-.018,-.071))
        anchors.extend((tuple(wrist),tuple(palm)));targets.extend((tuple(target_wrist),tuple(target_palm)))
        segments.append((wrist,palm,'hand.'+side))
        for digit in range(1,6):
            mapped=(4-(digit-1) if side=='R' else digit-2) if digit>1 else None
            proximal=('finger.'+str(mapped) if digit>1 else 'thumb')+'.'+side
            distal=('finger_tip.'+str(mapped) if digit>1 else 'thumb_tip')+'.'+side
            a=rig.data.bones[proximal];b=rig.data.bones[distal]
            original=[Vector(joints[f'{source_side}-finger-{digit}-{j}']) for j in (1,2,3,4)]
            # Preserve all three original phalange landmarks using the two
            # existing controls: the distal control spans both distal phalanges.
            desired=[a.head_local,a.tail_local,b.head_local.lerp(b.tail_local,.52),b.tail_local]
            anchors.extend(tuple(v) for v in original);targets.extend(tuple(v) for v in desired)
            segments.extend(((original[0],original[1],proximal),(original[1],original[2],distal),(original[2],original[3],distal)))
            segments.append((palm,original[0],'hand.'+side))
        # A normal-axis pair fixes palm thickness and avoids a coplanar fit.
        index=Vector(joints[f'{source_side}-finger-2-1']);pinky=Vector(joints[f'{source_side}-finger-5-1'])
        normal=(index-wrist).cross(pinky-wrist).normalized()
        if normal.x<0:normal=-normal
        for sign in (-1,1):
            anchors.append(tuple(palm+normal*(.18*sign)))
            targets.append(tuple(target_palm+Vector((0,.023*sign,0))))
        direction=(palm-wrist).normalized()
        anchors.append(tuple(wrist-direction*.6));targets.append(tuple(target_wrist+Vector((0,.045,.09))))
        src=np.array(anchors,dtype=float);dst=np.array(targets,dtype=float);n=len(src)
        kernel=np.linalg.norm(src[:,None,:]-src[None,:,:],axis=2)
        affine=np.column_stack((np.ones(n),src))
        lhs=np.block([[kernel+np.eye(n)*1e-7,affine],[affine.T,np.zeros((4,4))]])
        coefficients=np.linalg.solve(lhs,np.vstack((dst,np.zeros((4,3)))))
        original=np.array(part['vertices'],dtype=float)
        fitted=np.column_stack((np.linalg.norm(original[:,None,:]-src[None,:,:],axis=2),np.ones(len(original)),original)) @ coefficients
        if not np.isfinite(fitted).all():raise RuntimeError('hand fit contains nonfinite coordinates')
        error=float(np.max(np.linalg.norm(np.column_stack((kernel,np.ones(n),src)) @ coefficients-dst,axis=1)))
        if error>1e-4:raise RuntimeError('hand landmarks did not fit')
        obj=hero.mesh(bpy,'June_Hand_'+side,fitted.tolist(),part['faces'],material)
        names={name for a,b,name in segments};groups={name:obj.vertex_groups.new(name=name) for name in names}
        for i,point in enumerate(original):
            p=Vector(point);distances={}
            for a,b,name in segments:
                d=b-a;t=max(0,min(1,(p-a).dot(d)/max(d.length_squared,1e-8)))
                distance=(p-a-d*t).length
                distances[name]=min(distances.get(name,float('inf')),distance)
            candidates=sorted(distances.items(),key=lambda v:v[1])[:3]
            weighted={name:1/(distance+.045)**5 for name,distance in candidates}
            total=sum(weighted.values())
            for name,w in weighted.items():groups[name].add([i],w/total,'REPLACE')
        mod=obj.modifiers.new('Articulated anatomical hand','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=True
        mod=obj.modifiers.new('Hand surface subdivision','SUBSURF');mod.levels=2;mod.render_levels=2
        obj['ce_hand_fit_max_landmark_error']=error
        obj['ce_hand_source']='CC0 continuous palm, knuckles and digits'
