"""Focused v4 sculpt and eyelid fit, from a verified studio-v3 checkpoint."""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.blender import june_hero_v9 as hero
from pipeline.blender import june_studio_assets as studio
from pipeline.blender import refine_june_studio as v2
from pipeline.blender import refine_june_studio_v3 as v3
from pipeline.blender import render_vertical_slice as base
from pipeline.june_studio import atomic_json, sha256


def face_field(point):
    from mathutils import Vector
    x,y,z=point
    front=hero.smooth((-y-.12)/.11)
    cheek=hero.gauss(abs(x),z,.137,2.650,.074,.060)*front
    y-=.013*cheek
    nose=hero.gauss(x,z,0,2.638,.057,.051)*front
    x*=1+.22*nose
    y+=.004*nose
    z+=.003*nose
    return Vector((x,y,z))


def refine_face(bpy,rig,head):
    """Smooth selected planes, retaining source topology and speech deltas."""
    from mathutils import Vector
    from mathutils.kdtree import KDTree
    keys=head.data.shape_keys.key_blocks
    world=head.matrix_world.copy();inverse=world.inverted()
    points=[world@p.co for p in keys['Basis'].data]
    neighbors=[set() for _ in points]
    for e in head.data.edges:
        a,b=e.vertices;neighbors[a].add(b);neighbors[b].add(a)
    weights=[]
    for x,y,z in points:
        mask=hero.gauss(abs(x),z,.145,2.652,.081,.065)*hero.smooth((-y-.12)/.10)
        mask*=1-hero.smooth((z-2.695)/.030)
        weights.append(mask)
    smoothed=[p.copy() for p in points]
    for _ in range(9):
        updated=[]
        for p,near,w in zip(smoothed,neighbors,weights):
            if not near or w<.001:updated.append(p.copy());continue
            mean=sum((smoothed[i] for i in near),Vector())/len(near)
            delta=mean-p
            updated.append(p+Vector((delta.x*.14,delta.y*.46,delta.z*.14))*w)
        smoothed=updated
    deltas=[q-p for p,q in zip(points,smoothed)]
    tree=KDTree(len(points))
    for i,p in enumerate(points):tree.insert(p,i)
    tree.balance()
    def fit(point):
        if point.y>-.10 or not 2.49<point.z<2.80:return point.copy()
        near=tree.find_n(point,4);weights=[1/max(d,.002)**2 for _,_,d in near]
        delta=sum((deltas[i]*w for (_,i,_),w in zip(near,weights)),Vector())/sum(weights)
        return face_field(point+delta)
    for obj in list(bpy.data.objects):
        if obj.parent is rig and obj.parent_bone=='head' and obj.type in ('MESH','CURVE'):
            # Preserve the proven rigid oral assembly and its fit.
            if obj.name.startswith('June_V3_'):continue
            v2.transform_geometry(obj,fit)
    # Open the neutral lids slightly; preserve the prior full-close endpoint.
    for side in ('L','R'):
        blink=keys['blink_'+side]
        delta=[p.co-b.co for p,b in zip(blink.data,keys['Basis'].data)]
        for key in keys:
            if key.name=='blink_'+side:continue
            for p,d in zip(key.data,delta):p.co-=d*.10
        # A closed lid needs enough anterior volume over the rotating iris.
        for p in blink.data:
            q=world@p.co
            if (q.x<0)!=(side=='L'):continue
            mask=hero.gauss(abs(q.x),q.z,.11,2.728,.085,.067)*hero.smooth((-q.y-.15)/.10)
            q.y-=.009*mask
            p.co=inverse@q
    for p,b in zip(head.data.vertices,keys['Basis'].data):p.co=b.co
    # Fit the complete eye assembly deeper; no visibility switches or eye hiding.
    for obj in bpy.data.objects:
        if obj.parent is rig and obj.parent_bone in ('eye.L','eye.R') and obj.type in ('MESH','CURVE'):
            v2.transform_geometry(obj,lambda p:p+Vector((0,.009,0)))
    v2.rest_attributes(head)
    head['ce_art_refinement']='studio-v4: softened cheek planes, rounded nose, open rest lids and fitted blink volume'
    return {'smoothing_iterations':9,'maximum_cheek_relaxation':max(d.length for d in deltas),
            'eye_assembly_inset':.009,'closed_lid_volume':.009,'neutral_lid_opening':.10}


def soften_groom_and_skin(bpy):
    # Preserve v3 strand identity and animation; soften the uniform pointed tips.
    for name in ('June_Studio_Beard','June_Studio_Moustache'):
        obj=bpy.data.objects[name]
        for spline in obj.data.splines:
            count=len(spline.points)
            for j,p in enumerate(spline.points):p.radius*=1-.30*(j/max(1,count-1))**2
    mat=bpy.data.materials['June V3 mapped aged skin']
    bs=mat.node_tree.nodes.get('Principled BSDF')
    for node in mat.node_tree.nodes:
        if node.type=='MIX_RGB' and node.blend_type=='MULTIPLY':
            node.inputs[2].default_value=(.68,.75,.79,1)
    bs.inputs['Subsurface Weight'].default_value=.12
    bs.inputs['Roughness'].default_value=.57


def fit_wardrobe(bpy,rig):
    """Lower the shoulder hump and fit collar edges against the actual coat."""
    from mathutils import Vector
    coat=bpy.data.objects['June_Continuous_Coat']
    def shoulder(point):
        x,y,z=point
        weight=math.exp(-((abs(x)-.355)/.14)**2)*hero.smooth((z-2.01)/.13)
        return Vector((x,y,z-.067*weight))
    v2.transform_geometry(coat,shoulder)
    shirt=bpy.data.objects['June_Plaid_Torso']
    def neckline(point):
        x,y,z=point;t=hero.smooth((z-2.06)/.17)
        return Vector((x*(1-.38*t),.014+(y-.014)*(1-.20*t),
                       z-.025*t*math.exp(-(x/.07)**2)*hero.smooth((-y-.04)/.06)))
    v2.transform_geometry(shirt,neckline)
    bpy.context.view_layer.update();surface=v2.head_surface(bpy,coat)
    def collar_fit(point):
        x,y,z=point
        # Retain the neck-side rolled edge; lay the outer/lower leaf on the coat.
        weight=hero.smooth((abs(x)-.115)/.11)*(1-.25*hero.smooth((z-2.19)/.05))
        hit,_,_,_=surface.ray_cast(Vector((x,-1,z)),Vector((0,1,0)),2.)
        if hit is not None:y+=(hit.y-.009-y)*weight*.90
        z-=.028*hero.smooth((abs(x)-.15)/.12)
        return Vector((x,y,z))
    for side in ('L','R'):
        for name in ('June_Jacket_Collar_'+side,'June_V2_Collar_Seam_'+side):
            v2.transform_geometry(bpy.data.objects[name],collar_fit)
    # A broader plaid band reads as woven flannel instead of a wire grid.
    mat=bpy.data.materials['June v9 plaid']
    ramp=mat.node_tree.nodes.get('CE_Plaid_Color').color_ramp
    ramp.elements[0].position=.34;ramp.elements[0].color=(.026,.038,.044,1)
    ramp.elements[1].position=.66;ramp.elements[1].color=(.075,.083,.083,1)
    if len(ramp.elements)>2:
        ramp.elements[2].position=.93;ramp.elements[2].color=(.105,.067,.046,1)
    for obj in (coat,shirt):v2.rest_attributes(obj)
    return {'shoulder_drop_max':.067,'collars_fitted_to_evaluated_coat':True,
            'shirt_neckline_taper':.38,'cloth_simulation':False}


def main():
    import bpy
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    p.add_argument('--views',default='');p.add_argument('--width',type=int,default=960);p.add_argument('--samples',type=int,default=16)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    source,output=Path(args.source).resolve(),Path(args.output).resolve()
    receipt=json.loads(source.with_suffix('.json').read_text())
    if receipt.get('asset_version')!='studio-v3' or source.parent==output.parent:
        raise ValueError('v4 requires an unchanged studio-v3 source in a separate directory')
    if sha256(source)!=receipt['asset_sha256']:raise ValueError('source asset identity mismatch')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    rig=bpy.data.objects['June_Oxley_Rig'];head=bpy.data.objects['June_Head'];scene=bpy.context.scene
    rig.data.pose_position='REST'
    for k in head.data.shape_keys.key_blocks:k.value=0
    bpy.context.view_layer.update()
    print('Sculpting v4 face and eyelid volume',flush=True)
    face_report=refine_face(bpy,rig,head);soften_groom_and_skin(bpy)
    print('Fitting shoulder and collar forms',flush=True)
    wardrobe_report=fit_wardrobe(bpy,rig)
    oral_report=v3.validate_oral(bpy,head)
    rig.data.pose_position='POSE';studio.body_pose(rig,270)
    rig['ce_asset_version']='studio-v4-development';rig['ce_dialogue_ready']=False
    collection=bpy.data.collections[receipt['character_collection']];collection.name='June_Character_Studio_v4'
    scene['ce_production_approved']=False
    scene.camera=bpy.data.objects['June_Camera_Close'];studio.aim_control(rig,'gaze',scene.camera.location)
    scene.frame_set(1);scene.render.resolution_x=args.width;scene.render.resolution_y=args.width*9//16
    scene.render.resolution_percentage=100;scene.cycles.samples=args.samples;scene.cycles.use_denoising=True
    scene.render.use_persistent_data=True;scene.render.image_settings.file_format='PNG'
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
    result={**receipt,'asset_version':'studio-v4','asset_sha256':sha256(output),'source_asset_sha256':sha256(source),
            'refinement_sha256':sha256(__file__),'character_collection':collection.name,
            'face_report':face_report,'wardrobe_report':wardrobe_report,'oral_report':oral_report,
            'production_approved':False,'dialogue_quality_approved':False}
    atomic_json(output.with_suffix('.json'),result)
    views={'close':('Close',{}),'front':('Front',{}),'wide':('Wide',{}),
           'blink':('Close',{'blink_L':1.,'blink_R':1.}),
           'smile':('Close',{'smile':.75,'warm_eyes':.65}),'speech-d':('Close',{'D':1.})}
    for label in filter(None,args.views.split(',')):
        camera,values=views[label]
        for k in head.data.shape_keys.key_blocks:k.value=values.get(k.name,0)
        scene.camera=bpy.data.objects['June_Camera_'+camera];studio.aim_control(rig,'gaze',scene.camera.location)
        scene.render.filepath=str(output.parent/(label+'.png'))
        print('Rendering v4 '+label,flush=True);bpy.ops.render.render(write_still=True)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
