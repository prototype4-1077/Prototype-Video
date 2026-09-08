"""June v9 development sculpture, built as turnable geometry, never image cards.

The v8 named control rig is retained. This opt-in asset is an art-development
candidate, not an approved replacement or a certified dialogue rig.
"""
import math
import random

from pipeline.blender import render_vertical_slice as base

TAU = math.tau
PROFILE = (
    (2.285, .025, .060, .030), (2.32, .125, .143, .072),
    (2.39, .191, .184, .110), (2.48, .219, .202, .147),
    (2.59, .252, .217, .179), (2.69, .265, .227, .207),
    (2.78, .263, .234, .224), (2.90, .269, .230, .239),
    (3.00, .245, .205, .225), (3.075, .165, .143, .158),
    (3.115, .012, .014, .018),
)


def blend(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = min(1., max(0., t))
    return t*t*(3-2*t)


def profile(z, table=PROFILE):
    """Cubic Hermite cross sections with local slopes, including both endpoints."""
    if z <= table[0][0]:
        return table[0][1:]
    if z >= table[-1][0]:
        return table[-1][1:]
    for i, (a, b) in enumerate(zip(table, table[1:])):
        if a[0] <= z <= b[0]:
            t = (z-a[0])/(b[0]-a[0]); h = b[0]-a[0]
            p, q = table[max(0, i-1)], table[min(len(table)-1, i+2)]
            return tuple((2*t**3-3*t*t+1)*a[k] + (t**3-2*t*t+t)*h*(b[k]-p[k])/(b[0]-p[0])
                         + (-2*t**3+3*t*t)*b[k] + (t**3-t*t)*h*(q[k]-a[k])/(q[0]-a[0])
                         for k in range(1, len(a)))
    raise ValueError(z)


def gauss(x, z, cx, cz, wx, wz):
    return math.exp(-((x-cx)/wx)**2 - ((z-cz)/wz)**2)


def face_y(x, z):
    rx, depth, _ = profile(z)
    front = math.sqrt(max(0., 1-(x/max(rx,.001))**2))
    # Continuous nose bridge, drooping tip, malar planes, muzzle and chin.
    displacement = (
        .077*gauss(x,z,.006,2.737,.044,.113)
        +.143*gauss(x,z,.009,2.641,.061,.070)
        +.030*gauss(x,z,0,2.603,.085,.027)
        +.052*gauss(x,z,-.164,2.658,.072,.078)
        +.046*gauss(x,z,.156,2.644,.076,.074)
        +.043*gauss(x,z,.003,2.500,.142,.077)
        +.033*gauss(x,z,.005,2.389,.110,.060)
        -.017*gauss(x,z,-.107,2.761,.072,.052)
        -.017*gauss(x,z,.107,2.757,.072,.052)
        -.013*gauss(x,z,-.201,2.537,.046,.082)
        -.011*gauss(x,z,.201,2.537,.046,.082)
        +.020*gauss(x,z,-.107,2.845,.081,.030)
        +.018*gauss(x,z,.107,2.841,.081,.030)
    )
    crease=0.
    for k in range(4):
        zz=2.90+k*.031+.004*math.cos(x*21)+.001*math.sin(x*77+k)
        crease+=.0012*math.exp(-((z-zz)/.0022)**2)*math.exp(-(x/(.18-k*.02))**6)
    return -depth*front-displacement*front+crease


def mesh(bpy, name, vertices, faces, material, *, sub=0):
    data=bpy.data.meshes.new(name+'_Mesh')
    data.from_pydata(vertices,[],faces);data.update()
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj)
    base._assign(obj,material);base._smooth(obj)
    if sub:
        mod=obj.modifiers.new('Sculpt surface subdivision','SUBSURF')
        mod.levels=sub;mod.render_levels=sub
    obj['ce_asset_version']='v9-development'
    return obj


def curves(bpy, name, paths, material, radius, rig=None, bone='head'):
    data=bpy.data.curves.new(name+'_Curves','CURVE')
    data.dimensions='3D';data.resolution_u=2
    data.bevel_depth=radius;data.bevel_resolution=2
    for path in paths:
        spline=data.splines.new('POLY');spline.points.add(len(path)-1)
        for i,(point,co) in enumerate(zip(spline.points,path)):
            point.co=(*co[:3],1.)
            point.radius=co[3] if len(co)>3 else blend(1.,.12,i/max(1,len(path)-1))
    obj=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(obj)
    base._assign(obj,material)
    if rig is not None:base._parent_to_bone(obj,rig,bone)
    obj['ce_asset_version']='v9-development'
    return obj


def materials(bpy):
    specs={
        'skin':((.43,.195,.092,1),.48), 'crease':((.30,.120,.055,1),.57),
        'lip':((.36,.135,.080,1),.51), 'mouth':((.035,.008,.006,1),.68),
        'hair':((.62,.592,.530,1),.52), 'hair_base':((.41,.385,.33,1),.76),
        'eye':((.80,.82,.72,1),.19), 'iris':((.12,.26,.285,1),.27),
        'iris_rim':((.018,.048,.055,1),.27), 'pupil':((.003,.005,.006,1),.12),
        'denim':((.019,.049,.078,1),.77), 'overalls':((.011,.023,.032,1),.80),
        'plaid':((.041,.080,.108,1),.79), 'thread':((.30,.185,.075,1),.8),
        'brass':((.24,.137,.042,1),.32), 'leather':((.095,.052,.025,1),.64),
        'sole':((.024,.020,.014,1),.82), 'nail':((.51,.30,.19,1),.4),
    }
    result={}
    for key,(color,rough) in specs.items():
        mat=base._material(bpy,'June v9 '+key,color,roughness=rough)
        result[key]=mat;nodes=mat.node_tree.nodes;links=mat.node_tree.links
        bs=nodes.get('Principled BSDF')
        bs.inputs['Specular IOR Level'].default_value=.32
        if key=='brass':bs.inputs['Metallic'].default_value=.8
        if key in ('skin','lip','crease','nail'):
            bs.inputs['Subsurface Weight'].default_value=.09
            bs.inputs['Subsurface Radius'].default_value=(1.,.46,.22)
            bs.inputs['Subsurface Scale'].default_value=.022
        if key in ('skin','denim','overalls','plaid','leather'):
            noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=180 if key=='skin' else 110
            noise.inputs['Detail'].default_value=2
            bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.22
            bump.inputs['Distance'].default_value=.0014 if key=='skin' else .001
            links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bs.inputs['Normal'])
            tone=nodes.new('ShaderNodeValToRGB')
            tone.color_ramp.elements[0].color=tuple(c*.70 for c in color[:3])+(1.,)
            tone.color_ramp.elements[1].color=tuple(c*1.18 for c in color[:3])+(1.,)
            links.new(noise.outputs['Fac'],tone.inputs['Fac']);links.new(tone.outputs['Color'],bs.inputs['Base Color'])
        if key in ('denim','overalls','plaid'):
            bs.inputs['Sheen Weight'].default_value=.21
            bs.inputs['Sheen Roughness'].default_value=.65
    base._plaid_shader(result['plaid'],(.035,.068,.089,1),(.083,.119,.141,1))
    return result


def eyes(bpy, rig, mats, *, anatomical=False):
    face={'eyes':[],'upper_lids':[],'lower_lids':[],'brows':[]}
    rng=random.Random(309)
    for side,cx,cz in (('L',-.107,2.761),('R',.107,2.757)):
        if anatomical:cz-=.030
        cy=-.2445 if anatomical else -.202
        eye=base._sphere(bpy,'June_Eye_'+side,(cx,cy,cz),(.071,.050,.059),mats['eye'],segments=64,rings=40)
        base._parent_to_bone(eye,rig,'eye.'+side)
        face['eyes'].append(eye)
        shift=-.0425 if anatomical else 0.
        for name,r,depth,mat in (('Iris_Rim',.029,-.251+shift,'iris_rim'),('Iris',.026,-.253+shift,'iris'),('Pupil',.012,-.256+shift,'pupil')):
            o=base._sphere(bpy,'June_'+name+'_'+side,(cx,depth,cz), (r,.0028,r),mats[mat],segments=64,rings=32)
            base._parent_to_bone(o,rig,'eye.'+side);face['eyes'].append(o)
        fibres=[]
        for j in range(130):
            a=TAU*j/130;r1=rng.uniform(.013,.017);r2=rng.uniform(.021,.0255)
            fibres.append([(cx+r*math.cos(a),-.2557+shift,cz+r*math.sin(a),.45) for r in (r1,(r1+r2)/2,r2)])
        curves(bpy,'June_Iris_Fibres_'+side,fibres,mats['iris_rim'],.00023,rig,'eye.'+side)
        for upper in (() if anatomical else (True,False)):
            verts=[];polys=[];n=96;rows=7
            for k in range(rows):
                t=k/(rows-1)
                for j in range(n+1):
                    a=math.pi*j/n*(1 if upper else -1)
                    x=cx+blend(.061,.095,t)*math.cos(a)
                    z=cz+blend(.033,.077 if upper else .067,t)*math.sin(a)
                    sphere_y=cy-.050*math.sqrt(max(0.,1-((x-cx)/.071)**2-((z-cz)/.059)**2))
                    y=min(face_y(x,z)-.002,sphere_y-.003)-.005*math.sin(math.pi*t)
                    verts.append((x,y,z))
            for k in range(rows-1):
                for j in range(n):
                    q=k*(n+1)+j;polys.append((q,q+1,q+n+2,q+n+1))
            name='June_Eyelid_'+('Upper_' if upper else 'Lower_')+side
            o=mesh(bpy,name,verts,polys,mats['skin'],sub=1)
            o.shape_key_add(name='Basis');blink=o.shape_key_add(name='blink')
            for i,p in enumerate(blink.data):
                k,j=divmod(i,n+1);t=k/(rows-1)
                a=math.pi*j/n
                p.co.z-=((.056 if upper else -.009)*math.sin(a)*(1-smooth(t)))
                p.co.y-=.014*math.sin(a)*(1-smooth(t))
            base._parent_to_bone(o,rig,'head')
            face['upper_lids' if upper else 'lower_lids'].append(o)
            rim=[]
            for j in range(65):
                a=math.pi*j/64*(1 if upper else -1)
                x=cx+.061*math.cos(a);z=cz+.033*math.sin(a)
                y=min(face_y(x,z)-.003,cy-.050*math.sqrt(max(0.,1-((x-cx)/.071)**2-((z-cz)/.059)**2))-.004)
                rim.append((x,y,z,.45*math.sin(math.pi*j/64)+.2))
            curves(bpy,'June_Lid_Rim_'+side+str(upper),[rim],mats['crease'],.0015,rig)
        # Arched white brows with a groomed surface and independent filaments.
        browpaths=[]
        for j in range(130):
            t=rng.random();x=cx+blend(-.079,.075,t)
            z=cz+.085+.016*math.sin(math.pi*t)+rng.uniform(-.006,.006)
            path=[]
            for k in range(6):
                u=k/5;xx=x+.016*u;zz=z+.009*math.sin(u*2.3)
                path.append((xx,face_y(xx,zz)-.010-.006*math.sin(u*math.pi),zz,1-u*.93))
            browpaths.append(path)
        face['brows'].append(curves(bpy,'June_Brow_'+side,browpaths,mats['hair'],.0009,rig))
    return face


def loft(bpy,name,sections,mat,*,arc=(0,TAU),segments=96,rows=64,thickness=0):
    verts=[];faces=[]
    for k in range(rows+1):
        z=blend(sections[0][0],sections[-1][0],k/rows)
        rx,ry,cy=profile(z,sections)
        for j in range(segments+1):
            a=blend(*arc,j/segments)
            ripple=.0018*math.sin(a*11+z*39)*math.sin(a*3-z*17)
            verts.append(((rx+ripple)*math.sin(a),cy-(ry+ripple)*math.cos(a),z))
    for k in range(rows):
        for j in range(segments):
            q=k*(segments+1)+j;faces.append((q,q+1,q+segments+2,q+segments+1))
    o=mesh(bpy,name,verts,faces,mat,sub=1)
    if thickness:
        mod=o.modifiers.new('Garment thickness','SOLIDIFY');mod.thickness=thickness
    return o


def panel(bpy, name, boundary, mat, rig, bone='torso', thickness=.007):
    # Subdivided cloth panels use a center fan with inset support at the hem.
    n=len(boundary);center=tuple(sum(p[k] for p in boundary)/n for k in range(3))
    verts=[center]+[tuple(blend(center[k],p[k],.94) for k in range(3)) for p in boundary]+list(boundary)
    faces=[(0,1+j,1+(j+1)%n) for j in range(n)]
    faces += [(1+j,n+1+j,n+1+(j+1)%n,1+(j+1)%n) for j in range(n)]
    o=mesh(bpy,name,verts,faces,mat,sub=2)
    crease=o.data.attributes.new('crease_edge','FLOAT','EDGE')
    for edge in o.data.edges:
        if all(i>=n+1 for i in edge.vertices):crease.data[edge.index].value=.8
    mod=o.modifiers.new('Fabric thickness','SOLIDIFY');mod.thickness=thickness
    base._parent_to_bone(o,rig,bone)
    return o


def seam(bpy,name,points,mat,rig,bone='torso',radius=.001):
    # Every stitch is explicit geometry, fixed to the same deforming surface.
    from mathutils import Vector
    paths=[]
    for a,b in zip(points,points[1:]):
        a,b=Vector(a),Vector(b);n=max(1,int((b-a).length/.009))
        for j in range(n):paths.append([(*a.lerp(b,j/n),.8),(*a.lerp(b,(j+.52)/n),.8)])
    return curves(bpy,name,paths,mat,radius,rig,bone)


def weighted_fabric(bpy, mathutils, name, points, radii, weights, rig, material, segments=48):
    """Parallel-transport ring frames avoid the legacy reference-axis knee flip."""
    from mathutils import Vector
    obj=base._weighted_chain_surface(bpy,mathutils,name,points,radii,weights,rig,material,radial_segments=segments)
    path=[Vector(p) for p in points];previous_t=None;axis=None
    minimum_dot=1.
    for k,(p,r) in enumerate(zip(path,radii)):
        t=(path[min(k+1,len(path)-1)]-path[max(0,k-1)]).normalized()
        if previous_t is None:
            reference=Vector((1,0,0)) if abs(t.x)<.9 else Vector((0,1,0))
            axis=(reference-t*reference.dot(t)).normalized()
        else:
            new_axis=previous_t.rotation_difference(t) @ axis
            minimum_dot=min(minimum_dot,axis.dot(new_axis))
            axis=new_axis
        cross=t.cross(axis).normalized()
        for j in range(segments):
            a=TAU*j/segments
            obj.data.vertices[k*segments+j].co=p+r*(axis*math.cos(a)+cross*math.sin(a))
        previous_t=t
    obj['ce_ring_frame_transport']='minimum_rotation'
    obj['ce_minimum_adjacent_ring_axis_dot']=minimum_dot
    return obj


def garments(bpy, mathutils, rig, mats):
    shirt=((1.26,.277,.191,.025),(1.53,.289,.204,.02),(1.89,.318,.210,.018),(2.12,.302,.186,.018),(2.23,.210,.144,.015))
    jacket=((1.28,.312,.220,.022),(1.36,.316,.225,.020),(1.66,.333,.234,.025),(1.94,.354,.234,.025),(2.11,.337,.209,.024),(2.24,.211,.163,.027))
    o=loft(bpy,'June_Plaid_Torso',shirt,mats['plaid']);base._parent_to_bone(o,rig,'torso')
    o=loft(bpy,'June_Denim_Jacket_Shell',jacket,mats['denim'],arc=(.43,TAU-.43),thickness=.009)
    base._parent_to_bone(o,rig,'torso')
    o=loft(bpy,'June_Overall_Waist',((1.08,.275,.205,.003),(1.20,.293,.216,.010),(1.35,.292,.216,.018),(1.43,.285,.210,.018)),mats['overalls'])
    base._parent_to_bone(o,rig,'pelvis')
    panel(bpy,'June_Overall_Bib',[(-.204,-.189,1.43),(-.200,-.188,1.81),(-.15,-.239,1.84),(.15,-.239,1.84),(.20,-.188,1.81),(.204,-.189,1.43),(0,-.244,1.43)],mats['overalls'],rig)
    for sign,side in ((-1,'L'),(1,'R')):
        # Downturned jacket collar and shirt collar, both actual fabric patches.
        panel(bpy,'June_Jacket_Collar_'+side,[(sign*.102,-.144,2.246),(sign*.166,-.175,2.24),(sign*.285,-.156,2.154),(sign*.219,-.223,2.057),(sign*.13,-.207,2.179)],mats['denim'],rig)
        panel(bpy,'June_Shirt_Collar_'+side,[(sign*.035,-.130,2.247),(sign*.102,-.154,2.227),(sign*.125,-.206,2.112),(sign*.069,-.219,2.133)],mats['plaid'],rig)
        for z in (1.38,1.59,1.80,2.005):
            rx,ry,cy=profile(z,jacket);x=sign*rx*math.sin(.47);y=cy-ry*math.cos(.47)-.006
            o=base._sphere(bpy,'June_Jacket_Button_'+side+str(z),(x,y,z),(.015,.004,.015),mats['brass'],segments=24,rings=12)
            base._parent_to_bone(o,rig,'torso')
        path=[]
        for j in range(61):
            z=blend(1.30,2.14,j/60);rx,ry,cy=profile(z,jacket)
            path.append((sign*rx*math.sin(.465),cy-ry*math.cos(.465)-.006,z))
        seam(bpy,'June_Jacket_Front_Stitches_'+side,path,mats['thread'],rig)
        pocket=[(sign*.189,-.210,1.895),(sign*.285,-.149,1.890),(sign*.28,-.157,1.757),(sign*.235,-.193,1.727),(sign*.186,-.215,1.766)]
        panel(bpy,'June_Jacket_Pocket_'+side,pocket,mats['denim'],rig)
        seam(bpy,'June_Pocket_Stitches_'+side,[ (x,y-.006,z) for x,y,z in pocket]+[(pocket[0][0],pocket[0][1]-.006,pocket[0][2])],mats['thread'],rig)
        strap=[(sign*.139,-.219,1.79),(sign*.168,-.205,1.79),(sign*.174,-.177,2.14),(sign*.145,-.191,2.16)]
        panel(bpy,'June_Overall_Strap_'+side,strap,mats['overalls'],rig)
        curves(bpy,'June_Overall_Buckle_'+side,[[(sign*.136,-.226,1.849),(sign*.172,-.208,1.849),(sign*.172,-.208,1.810),(sign*.136,-.226,1.810),(sign*.136,-.226,1.849)]],mats['brass'],.003,rig,'torso')
    pocket=[(-.089,-.250,1.57),(-.089,-.250,1.734),(.089,-.250,1.734),(.089,-.250,1.57),(0,-.256,1.548)]
    panel(bpy,'June_Bib_Pocket',pocket,mats['overalls'],rig)
    seam(bpy,'June_Bib_Pocket_Seam',[(x,y-.005,z) for x,y,z in pocket],mats['thread'],rig)
    for z in (1.935,2.025,2.095):
        o=base._sphere(bpy,'June_Shirt_Button_'+str(z),(0,-.202,z),(.008,.003,.008),mats['brass'],segments=20,rings=12);base._parent_to_bone(o,rig,'torso')
    # Neck is tapered anatomy continuing underneath the collar.
    o=loft(bpy,'June_Neck',((2.17,.11,.096,.025),(2.25,.105,.10,.019),(2.37,.102,.111,.015),(2.43,.12,.115,.014)),mats['skin'],segments=64,rows=30)
    base._parent_to_bone(o,rig,'neck')
    for side in ('L','R'):
        for label,first,second,rad,mat in (
            ('Jacket_Sleeve','upper_arm.','forearm.',(.136,.118,.113,.101,.080),mats['denim']),
            ('Overall_Leg','thigh.','shin.',(.158,.152,.128,.118,.106),mats['overalls'])):
            a=rig.data.bones[first+side];b=rig.data.bones[second+side]
            points=[];radii=[];weights=[]
            # The proximal section remains with the shoulder/hip and blends into
            # the limb. Its cap stays underneath the torso garment in all poses.
            anchor=mathutils.Vector((a.head_local.x*.80,.015,2.13 if label=='Jacket_Sleeve' else 1.34))
            body_bone='clavicle.'+side if label=='Jacket_Sleeve' else 'pelvis'
            for j in range(8):
                t=j/8;w=smooth(t)
                points.append(anchor.lerp(a.head_local,t))
                radii.append(rad[0]*(.94+.06*t))
                weights.append({body_bone:1-w,first+side:w})
            for j in range(41):
                t=j/40
                p=a.head_local.lerp(a.tail_local,min(1,t*2)) if t<=.5 else b.head_local.lerp(b.tail_local,(t-.5)*2)
                idx=min(3,int(t*4));r=blend(rad[idx],rad[idx+1],t*4-idx)
                folds=.004*math.sin(t*TAU*9)*math.exp(-((t-.54)/.17)**2)+.003*math.sin(t*TAU*13)*smooth((t-.84)/.16)
                w=smooth((t-.37)/.26)
                points.append(p);radii.append(r+folds);weights.append({first+side:1-w,second+side:w})
            o=weighted_fabric(bpy,mathutils,'June_Weighted_'+label+'_'+side,points,radii,weights,rig,mat)
            o['ce_joint']='49_ring_weighted_fabric'
        bone=rig.data.bones['forearm.'+side];w=bone.tail_local;d=(bone.tail_local-bone.head_local).normalized()
        cuff=base._cylinder_between(bpy,mathutils,'June_Cuff_'+side,w-d*.051,w-d*.003,.083,mats['denim'])
        base._parent_to_bone(cuff,rig,'forearm.'+side)


def boots(bpy, mathutils, rig, mats):
    # Correct full-size soles: the old box helper's dimensions were half intended.
    for side,x in (('L',-.22),('R',.22)):
        o=base._sphere(bpy,'June_Boot_'+side,(x,-.746,.264),(.109,.200,.093),mats['leather'],segments=56,rings=32)
        base._parent_to_bone(o,rig,'foot.'+side)
        o=base._box(bpy,'June_Boot_Sole_'+side,(x,-.75,.185),(.218,.398,.035),mats['sole'],bevel=.033)
        base._parent_to_bone(o,rig,'foot.'+side)
        o=base._sphere(bpy,'June_Boot_Quarter_'+side,(x,-.635,.328),(.103,.102,.122),mats['leather'],segments=48,rings=32)
        base._parent_to_bone(o,rig,'foot.'+side)
        laces=[]
        for j in range(5):
            y=-.805+j*.026;z=.330+j*.014
            laces.append([(x-.036,y,z),(x+.032,y+.023,z+.008)])
            laces.append([(x+.036,y,z+.002),(x-.032,y+.023,z+.009)])
        curves(bpy,'June_Boot_Laces_'+side,laces,mats['sole'],.0027,rig,'foot.'+side)


def join_coat(bpy, rig, material):
    """Fuse the shoulder silhouette and transfer existing rest-space skin weights."""
    from mathutils.kdtree import KDTree
    originals=[bpy.data.objects[n] for n in ('June_Denim_Jacket_Shell','June_Weighted_Jacket_Sleeve_L','June_Weighted_Jacket_Sleeve_R')]
    bpy.context.view_layer.update();vertices=[];faces=[];samples=[]
    for obj in originals:
        lookup={g.index:g.name for g in obj.vertex_groups}
        for p in obj.data.vertices:
            weights={lookup[g.group]:g.weight for g in p.groups} or {'torso':1.}
            samples.append((obj.matrix_world @ p.co,weights))
        ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh();offset=len(vertices)
        vertices.extend(tuple(ev.matrix_world @ p.co) for p in m.vertices)
        faces.extend(tuple(offset+i for i in f.vertices) for f in m.polygons);ev.to_mesh_clear()
    obj=mesh(bpy,'June_Continuous_Coat',vertices,faces,material)
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new('Connected shoulder volume','REMESH');mod.mode='VOXEL';mod.voxel_size=.006
    bpy.ops.object.modifier_apply(modifier=mod.name)
    tree=KDTree(len(samples))
    for i,(p,w) in enumerate(samples):tree.insert(p,i)
    tree.balance();groups={name:obj.vertex_groups.new(name=name) for name in {n for p,w in samples for n in w}}
    for p in obj.data.vertices:
        weights={};total=0.
        for co,index,dist in tree.find_n(p.co,4):
            influence=1/max(.001,dist)**2;total+=influence
            for name,w in samples[index][1].items():weights[name]=weights.get(name,0)+w*influence
        for name,w in weights.items():groups[name].add([p.index],w/total,'REPLACE')
    mod=obj.modifiers.new('Coat deformation','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=True
    mod=obj.modifiers.new('Coat surface relaxation','SMOOTH');mod.factor=.3;mod.iterations=3
    mod=obj.modifiers.new('Coat surface finish','SUBSURF');mod.levels=1;mod.render_levels=1
    base._smooth(obj)
    for old in originals:bpy.data.objects.remove(old,do_unlink=True)
    obj['ce_garment_construction']='continuous_voxel_fused_shoulders_rest_weight_transfer'


def build(bpy, mathutils, legacy_materials=None):
    """Reuse the named v8 rig, replace its complete visible character geometry."""
    legacy_materials=legacy_materials or base._make_materials(bpy,asset_major=8)
    rig,_,_=base._make_june(bpy,mathutils,legacy_materials,asset_major=8)
    for obj in list(bpy.data.objects):
        if obj is rig:continue
        if obj.name.startswith('June_'):
            bpy.data.objects.remove(obj,do_unlink=True)
    # Eye pivots are fitted to the new eyeballs; existing gaze controller survives.
    bpy.context.view_layer.objects.active=rig;rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for side,x,z in (('L',-.107,2.761),('R',.107,2.757)):
        b=rig.data.edit_bones['eye.'+side];b.head=(x,-.2445,z-.030);b.tail=(x,-.3645,z-.030)
        # v8 digit pivots were offset sideways from their own wrist by .08 units.
        sign=-1 if side=='L' else 1
        captures=[]
        for digit in range(5):
            names=(f'finger.{digit}.{side}',f'finger_tip.{digit}.{side}') if digit<4 else ('thumb.'+side,'thumb_tip.'+side)
            for name in names:
                bone=rig.data.edit_bones[name];captures.append((bone,bone.head.copy(),bone.tail.copy(),bone.use_connect))
                bone.use_connect=False
        for bone,head_pos,tail_pos,connect in captures:
            head_pos.x+=sign*.08;tail_pos.x+=sign*.08;bone.head=head_pos;bone.tail=tail_pos
        for bone,head_pos,tail_pos,connect in captures:bone.use_connect=connect
    bpy.ops.object.mode_set(mode='OBJECT')
    mats=materials(bpy)
    from pipeline.blender.june_anatomy_source import fitted_head, groom, fitted_hands
    head_obj,surface_y,bvh=fitted_head(bpy,rig,mats['skin'])
    global face_y
    original_y=face_y
    face_y=surface_y
    try:
        face=eyes(bpy,rig,mats,anatomical=True)
        # Keep the named neutral-mouth interface without covering anatomical lips.
        oral=mesh(bpy,'June_Mouth_Viseme',[(0,0,2.5),(.001,0,2.5),(0,0,2.501)],[(0,1,2)],mats['mouth'])
        oral.shape_key_add(name='Basis');oral.shape_key_add(name='X')
        base._parent_to_bone(oral,rig,'head');oral['ce_dialogue_ready']=False
        groom(bpy,rig,head_obj,mats,bvh)
    finally:
        face_y=original_y
    garments(bpy,mathutils,rig,mats);fitted_hands(bpy,rig,mats['skin']);boots(bpy,mathutils,rig,mats)
    join_coat(bpy,rig,mats['denim'])
    rig['ce_asset_major']=9
    rig['ce_art_status']='development_not_identity_approved'
    rig['ce_dialogue_ready']=False
    rig['ce_groom_seed']=1907
    rig['ce_control_rig']='inherited_v8_named_body_controls_new_visible_meshes'
    return rig,oral,face
