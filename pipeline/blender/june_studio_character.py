"""Reusable June development asset with CC0 anatomical facial deformations.

The accepted drawings remain the identity targets. This builder exports an
editable asset; it does not declare the new sculpt or performance approved.
"""
import bisect
import gzip
import hashlib
import json
import math
import random
from pathlib import Path

from pipeline.blender import june_hero_v9 as hero
from pipeline.blender import june_anatomy_source as anatomy
from pipeline.blender import render_vertical_slice as base

EXPRESSIONS = {
    "A": {"mouth-compression": .55},
    "B": {"mouth-open": .11, "mouth-retraction": .12},
    "C": {"mouth-open": .32, "mouth-retraction": .12},
    "D": {"mouth-open": .62},
    "E": {"mouth-open": .28, "mouth-pursing": .25},
    "F": {"mouth-open": .16, "mouth-pursing": .68, "mouth-protusion": .18},
    "G": {"mouth-open": .09, "mouth-compression": .20, "mouth-retraction": .16},
    "H": {"mouth-open": .29},
    "X": {},
    "blink_L": {"eye-right-closure": 1.0},
    "blink_R": {"eye-left-closure": 1.0},
    "smile": {"mouth-corner-puller": .38, "mouth-upward-retraction": .28},
    "warm_eyes": {"eye-left-slit": .20, "eye-right-slit": .20},
    "brow_raise": {"eyebrows-left-up": .70, "eyebrows-right-up": .55},
    "concern": {"eyebrows-left-down": .35, "eyebrows-right-down": .28},
}


def load_targets():
    root = Path(__file__).resolve().parents[2] / "concept/characters/assets"
    path = root / "june_expression_cc0.json.gz"
    proof = json.loads((root / "june_expression_cc0_provenance.json").read_text())
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != proof["derived_sha256"]:
        raise ValueError("facial source archive identity mismatch")
    return json.loads(gzip.decompress(data))["targets"]


def fitted_point(point):
    """Fit source anatomy consistently in neutral and every expression.

    Shorten the v9 lower-face stretch, soften its jaw, and keep the established
    eye pivots and rig scale. No per-expression nearest-image fitting is used.
    """
    sx, sy, sz = point
    sign = 1 if sx >= 0 else -1
    cx, cz = sign * .293125, 7.85365
    distance = ((sx-cx)/.42)**2 + ((sy-cz)/.30)**2 + ((sz-1.21)/.40)**2
    weight = math.exp(-distance*distance)
    sx = cx + (sx-cx)*(1+.48*weight)
    sy = cz + (sy-cz)*(1+.78*weight)
    x, y, z = sx*.32 + sign*.013*weight, -(sz-.40)*.30, 2.761+(sy-cz)*.32
    if z > 2.86:
        z = 2.86+(z-2.86)*.84
    if z < 2.761:
        z = 2.761+(z-2.761)*1.16
    if z < 2.58:
        x *= 1-.065*hero.smooth((2.58-z)/.22)
    # Authored cheek volume and an intentionally uneven resting smile.
    cheek = hero.gauss(abs(x), z, .15, 2.65, .065, .09)
    x *= 1+.055*cheek
    if y < -.12:
        y -= .008*cheek
    if y < -.20:
        nose = hero.gauss(x,z,0,2.65,.062,.078)
        y -= .026*nose
        z -= .011*nose
    if z < 2.40:
        t = 1-hero.smooth((z-2.26)/.14)
        a = math.atan2(x/.15,-(y-.015)/.22)
        x = hero.blend(x,.105*math.sin(a),t)
        y = hero.blend(y,.015-.110*math.cos(a),t)
        z = max(2.22,z)
    return x,y,z


def sculpt_head(bpy, rig):
    from mathutils import Vector
    source = anatomy.load()["head"]
    targets = {name: {row[0]: Vector(row[1:]) for row in rows} for name,rows in load_targets().items()}
    source_points = [Vector(v) for v in source["vertices"]]
    # A small permanent smile belongs to this sculpt's neutral expression.
    for i, vertex_id in enumerate(source["source_vertex_ids"]):
        for name, amount in (("mouth-corner-puller", .10), ("mouth-upward-retraction", .045)):
            source_points[i] += targets[name].get(vertex_id,Vector((0,0,0))) * amount
    head = bpy.data.objects["June_Head"]
    head.shape_key_clear()
    for vertex, point in zip(head.data.vertices, source_points):
        vertex.co = fitted_point(point)
    head.shape_key_add(name="Basis")
    for name, mixture in EXPRESSIONS.items():
        key = head.shape_key_add(name=name)
        for i,(point,vertex_id) in enumerate(zip(source_points,source["source_vertex_ids"])):
            value = point.copy()
            for target,amount in mixture.items():
                value += targets[target].get(vertex_id,Vector((0,0,0))) * amount
            key.data[i].co = fitted_point(value)
    head["ce_expression_source"] = "Pinned MPFB CC0 anatomical target deltas"
    head["ce_mouth_shapes"] = "ABCDEFGHX"
    head["ce_speech_controls_complete"] = True
    head["ce_dialogue_ready"] = False
    for modifier in head.modifiers:
        if modifier.type == "SUBSURF":
            modifier.levels = 1
            modifier.render_levels = 2
    return head


def follow_face(obj, head):
    """Bind groom points to the head, so facial expressions move the follicles.

    Rest-space inverse-distance interpolation is stored as editable shape keys;
    no Python frame-change handler, runtime solver, or live network is needed.
    """
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    tree = KDTree(len(head.data.vertices))
    for vertex in head.data.vertices:
        tree.insert(vertex.co, vertex.index)
    tree.balance()
    obj.shape_key_add(name="Basis")
    points = obj.data.shape_keys.key_blocks["Basis"].data
    bindings = []
    for point in points:
        nearby = tree.find_n(Vector(point.co[:3]), 4)
        weights = [(index, 1/max(distance,.003)**2) for co,index,distance in nearby]
        total = sum(weight for _,weight in weights)
        bindings.append([(index,weight/total) for index,weight in weights])
    basis = head.data.shape_keys.key_blocks["Basis"]
    for name in EXPRESSIONS:
        if name == "X":
            continue
        source = head.data.shape_keys.key_blocks[name]
        delta = [p.co-b.co for p,b in zip(source.data,basis.data)]
        if max((d.length for d in delta), default=0) < 1e-8:
            continue
        key = obj.shape_key_add(name=name)
        for dest,rest,binding in zip(key.data,points,bindings):
            d = sum((delta[i]*w for i,w in binding), Vector((0,0,0)))
            dest.co = Vector(rest.co[:3]) + d
        curve = key.driver_add("value")
        variable = curve.driver.variables.new()
        variable.name = "face_value"
        variable.type = "SINGLE_PROP"
        target = variable.targets[0]
        target.id_type = "KEY"
        target.id = head.data.shape_keys
        target.data_path = 'key_blocks["'+name+'"].value'
        curve.driver.expression = "face_value"
    obj["ce_follows_facial_shapes"] = True


def groom(bpy, rig, head, mats):
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update()
    ev = head.evaluated_get(bpy.context.evaluated_depsgraph_get())
    evaluated = ev.to_mesh()
    evaluated.calc_loop_triangles()
    vertices = [v.co.copy() for v in evaluated.vertices]
    triangles = []
    for tri in evaluated.loop_triangles:
        a,b,c = (vertices[i] for i in tri.vertices)
        normal = (b-a).cross(c-a)
        if normal.length > 1e-10:
            triangles.append((a,b,c,normal.normalized(),normal.length/2))
    bvh = BVHTree.FromPolygons(vertices,[tuple(t.vertices) for t in evaluated.loop_triangles],all_triangles=True)
    ev.to_mesh_clear()
    rng = random.Random(4018)

    def masks(point):
        x,y,z = point
        angle = abs(math.atan2(x,-(y-.035)))
        hairline = 2.76 + .28*math.exp(-((angle-.7)/.85)**2)
        scalp = hero.smooth((z-hairline)/.028) * hero.smooth((angle-.63)/.25)
        top = 2.465 + .185*(1-math.exp(-(x/.15)**2))
        beard = hero.smooth((top-z)/.017)*hero.smooth((z-2.32)/.023)*hero.smooth((1.65-angle)/.15)
        # Reserve the lip opening. Use tapered edges instead of square masks.
        oral = math.exp(-(x/.088)**6-((z-2.488)/.019)**4)
        beard *= 1-oral
        moustache = math.exp(-(x/.105)**6-((z-(2.526-.10*abs(x)))/.014)**4) if y<-.15 else 0
        return {"Scalp":scalp,"Beard":beard,"Moustache":moustache}

    for category,count in (("Scalp",3000),("Beard",2600),("Moustache",650)):
        choices=[];cumulative=[];total=0
        for a,b,c,n,area in triangles:
            strength=masks((a+b+c)/3)[category]
            if strength>.003:
                total+=area*strength;choices.append((a,b,c,n));cumulative.append(total)
        if not choices:
            raise RuntimeError("empty fitted groom region: "+category)
        # A shaded undercoat supplies density; the strands supply the silhouette.
        # Feather its edge with a vertex attribute instead of a rectangular patch.
        under_vertices=[];under_faces=[];densities=[]
        for a,b,c,n,area in triangles:
            strength=masks((a+b+c)/3)[category]
            if strength>.13:
                offset=len(under_vertices)
                for point in (a,b,c):
                    under_vertices.append(tuple(point+n*.0022))
                    densities.append(masks(point)[category])
                under_faces.append((offset,offset+1,offset+2))
        material=base._material(bpy,'Studio '+category+' undercoat',(.43,.414,.365,1),roughness=.86)
        nodes=material.node_tree.nodes;links=material.node_tree.links;bs=nodes.get('Principled BSDF')
        attribute=nodes.new('ShaderNodeAttribute');attribute.attribute_name='groom_density'
        mix=nodes.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(.40,.205,.11,1);mix.inputs[2].default_value=(.48,.455,.402,1)
        links.new(attribute.outputs['Fac'],mix.inputs[0]);links.new(mix.outputs[0],bs.inputs['Base Color'])
        noise=nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=360
        bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.34;bump.inputs['Distance'].default_value=.001
        links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],bs.inputs['Normal'])
        under=hero.mesh(bpy,'June_Studio_'+category+'_Undercoat',under_vertices,under_faces,material)
        density=under.data.attributes.new('groom_density','FLOAT','POINT')
        for item,value in zip(density.data,densities):item.value=value
        base._parent_to_bone(under,rig,'head');follow_face(under,head)
        paths=[]
        for _ in range(count):
            a,b,c,normal=choices[bisect.bisect_left(cumulative,rng.random()*total)]
            u=math.sqrt(rng.random());v=rng.random();root=(1-u)*a+u*(1-v)*b+u*v*c
            sign=1 if root.x>=0 else -1
            if category=="Scalp":
                direction=Vector((sign*.30,.80,-.55));length=rng.uniform(.036,.075);lift=.012
            elif category=="Beard":
                direction=Vector((sign*.14,-.08,-1));length=rng.uniform(.022,.041);lift=.008
            else:
                direction=Vector((sign*.9,-.08,-.3));length=rng.uniform(.025,.044);lift=.010
            tangent=(direction-normal*normal.dot(direction)).normalized()
            path=[]
            for k in range(6):
                t=k/5;p=root+tangent*(t*length)
                nearest,n,_,_=bvh.find_nearest(p)
                p=nearest+n*(.0015+lift*math.sin(t*math.pi*.9))
                path.append((*p,1-t*.93))
            paths.append(path)
        obj=hero.curves(bpy,"June_Studio_"+category,paths,mats["hair"],.00085,rig)
        obj.data.bevel_resolution=0
        follow_face(obj,head)
    # Fine forehead creases follow the same facial shapes as the skin.
    crease_material=base._material(bpy,'Studio subtle age creases',(.26,.132,.075,1),roughness=.75)
    for row in range(4):
        path=[]
        for i in range(49):
            t=i/48;x=(t-.5)*(.30-row*.025);z=2.88+row*.025+.014*(x/.15)**2
            hit=bvh.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2)
            if hit[0] is not None:
                point=hit[0]+hit[1]*.0002
                path.append((*point,.15+.65*math.sin(math.pi*t)))
        obj=hero.curves(bpy,'June_Studio_Forehead_Crease_'+str(row),[path],crease_material,.00075,rig)
        obj.data.bevel_resolution=0;follow_face(obj,head)
    # Brows are sampled directly against the remodeled forehead.
    for sign,side in ((-1,"L"),(1,"R")):
        paths=[]
        for _ in range(120):
            t=rng.random();x=sign*.107+(t-.5)*.14;z=2.823+.020*math.sin(t*math.pi)+rng.uniform(-.004,.004)
            p,n,_,_=bvh.find_nearest(Vector((x,-.4,z)))
            paths.append([(*p+n*.003,1),(*(p+Vector((sign*.013,-.003,.006))),.1)])
        obj=hero.curves(bpy,"June_Studio_Brow_"+side,paths,mats["hair"],.0012,rig)
        obj.data.bevel_resolution=0
        follow_face(obj,head)


def finish_materials(bpy):
    for name in ("denim","overalls","plaid"):
        material=bpy.data.materials.get("June v9 "+name)
        nodes=material.node_tree.nodes;links=material.node_tree.links;bs=nodes.get("Principled BSDF")
        bs.inputs["Specular IOR Level"].default_value=.16
        bs.inputs["Sheen Weight"].default_value=.12
        bs.inputs["Roughness"].default_value=.83
        if name=="plaid":
            continue
        coordinates=nodes.new("ShaderNodeTexCoord")
        mapping=nodes.new("ShaderNodeVectorMath");mapping.operation="SCALE";mapping.inputs[3].default_value=1
        links.new(coordinates.outputs["Object"],mapping.inputs[0])
        wave=nodes.new("ShaderNodeTexWave");wave.bands_direction="DIAGONAL";wave.inputs["Scale"].default_value=230
        links.new(mapping.outputs["Vector"],wave.inputs["Vector"])
        bump=nodes.new("ShaderNodeBump");bump.inputs["Strength"].default_value=.25;bump.inputs["Distance"].default_value=.00065
        links.new(wave.outputs["Color"],bump.inputs["Height"]);links.new(bump.outputs["Normal"],bs.inputs["Normal"])
    skin=bpy.data.materials.get("June v9 skin").node_tree.nodes.get("Principled BSDF")
    skin.inputs["Roughness"].default_value=.58
    skin.inputs["Specular IOR Level"].default_value=.23
    hair=bpy.data.materials.get("June v9 hair").node_tree.nodes.get("Principled BSDF")
    hair.inputs["Base Color"].default_value=(.56,.535,.48,1)


def build(bpy, mathutils):
    rig, mouth, face=hero.build(bpy,mathutils)
    for obj in list(bpy.data.objects):
        if "Groom" in obj.name or "Undergroom" in obj.name or obj.name.startswith("June_Brow_") or obj is mouth or obj.name=='June_Neck':
            bpy.data.objects.remove(obj,do_unlink=True)
    head=sculpt_head(bpy,rig)
    mats={name:bpy.data.materials["June v9 "+name] for name in ("hair","skin","mouth","eye")}
    groom(bpy,rig,head,mats)
    neck=hero.loft(bpy,'June_Studio_Neck_Interior',((2.16,.086,.084,.014),(2.28,.09,.09,.014),(2.40,.094,.095,.014)),mats['skin'],segments=40,rows=12)
    base._parent_to_bone(neck,rig,'neck')
    # Rounded oral volume is behind the anatomical lip opening, never a face card.
    oral=base._sphere(bpy,"June_Studio_Oral_Cavity",(0,-.218,2.483),(.077,.045,.046),mats["mouth"],segments=32,rings=20)
    base._parent_to_bone(oral,rig,"head")
    tooth_material=base._material(bpy,'Studio aged ivory teeth',(.58,.545,.45,1),roughness=.4)
    for row,z in (('Upper',2.507),('Lower',2.466)):
        for i in range(8):
            x=(i-3.5)*.0158;y=-.276+.012*(x/.065)**2
            tooth=base._sphere(bpy,'June_Studio_'+row+'_Tooth_'+str(i),(x,y,z),(.008,.006,.010),tooth_material,segments=16,rings=10)
            bpy.context.view_layer.objects.active=tooth
            bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
            base._parent_to_bone(tooth,rig,'head')
            follow_face(tooth,head)
    finish_materials(bpy)
    coat=bpy.data.objects["June_Continuous_Coat"]
    before=len(coat.data.polygons)
    # Apply simplification at rest before any armature or smoothing modifier.
    bpy.ops.object.select_all(action="DESELECT");coat.select_set(True);bpy.context.view_layer.objects.active=coat
    decimate=coat.modifiers.new("Studio deformation mesh","DECIMATE");decimate.ratio=.20
    while coat.modifiers.find(decimate.name)>0:
        bpy.ops.object.modifier_move_up(modifier=decimate.name)
    bpy.ops.object.modifier_apply(modifier=decimate.name)
    coat["ce_source_face_count"]=before
    coat["ce_deformation_face_count"]=len(coat.data.polygons)
    rig["ce_asset_version"]="studio-v1-development"
    rig["ce_speech_controls_complete"]=True
    rig["ce_dialogue_ready"]=False
    rig["ce_art_status"]="development_not_identity_approved"
    return rig,head
