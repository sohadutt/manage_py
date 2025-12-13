import bpy
import bpy_extras
from mathutils import Vector, Matrix
from math import atan2
from math import radians
import os, shutil

s_f = 0
e_f = 23
bpy.context.scene.frame_current = s_f
bpy.context.scene.frame_start = s_f
bpy.context.scene.frame_end = e_f

FONT_PATH = r'C:\Users\pc\Desktop\script\blend addon\font\Assistant-VariableFont_wght.ttf'


def add_objects_to_holdout_collection(objects, collection_name='Holdout'):
    """
    Add objects to a holdout collection and enable holdout property.
    
    Args:
        objects: List of objects or single object to add to holdout
        collection_name: Name of the holdout collection
    """
    
    # Convert single object to list for consistent processing
    if not isinstance(objects, list):
        objects = [objects]
    
    # Get or create the collection
    if collection_name in bpy.data.collections:
        holdout_collection = bpy.data.collections[collection_name]
    else:
        holdout_collection = bpy.data.collections.new(collection_name)
        # Link to scene collection
        bpy.context.scene.collection.children.link(holdout_collection)
        print(f"Created new collection: '{collection_name}'")
    
    # Add objects to collection
    for obj in objects:
        # Remove object from its current collections
        for coll in obj.users_collection:
            coll.objects.unlink(obj)
        
        # Add to holdout collection
        holdout_collection.objects.link(obj)
        print(f"Added '{obj.name}' to holdout collection '{collection_name}'")
    
    # Enable holdout in view layer
    view_layer = bpy.context.view_layer
    
    def find_layer_collection(layer_collection, name):
        if layer_collection.name == name:
            return layer_collection
        for child in layer_collection.children:
            found = find_layer_collection(child, name)
            if found:
                return found
        return None
    
    target_layer_collection = find_layer_collection(view_layer.layer_collection, collection_name)
    
    if target_layer_collection:
        # Enable holdout for the collection in the active view layer
        target_layer_collection.holdout = True
        print(f"Holdout enabled for collection '{collection_name}' in view layer '{view_layer.name}'.")
    else:
        print(f"Warning: Collection '{collection_name}' not found in view layer hierarchy.")
    
    # Also set the collection's holdout property
    #holdout_collection.holdout = True
    
    return holdout_collection


def get_font_pixel_height(camera, obj):
    """Get the actual pixel height of a font object in camera view"""
    scene = bpy.context.scene
    
    # Get the evaluated object with all modifiers applied
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    
    # Get mesh data from text object
    mesh = eval_obj.to_mesh()
    
    # Transform vertices to world space
    world_vertices = [eval_obj.matrix_world @ v.co for v in mesh.vertices]
    
    # Project to camera view space
    projected = []
    for vertex in world_vertices:
        co_2d = bpy_extras.object_utils.world_to_camera_view(scene, camera, vertex)
        projected.append(co_2d)
    
    # Clean up
    eval_obj.to_mesh_clear()
    
    if not projected:
        return 0
    
    # Get Y range in screen space (0-1)
    min_y = min(p.y for p in projected)
    max_y = max(p.y for p in projected)
    
    # Convert to pixels
    render_height = scene.render.resolution_y
    pixel_height = (max_y - min_y) * render_height
    
    return pixel_height

def scale_font_objects_to_equal_height(target_pixel_height=30):
    """Scale all font objects to have the same pixel height in camera view"""
    
    scene = bpy.context.scene
    camera = scene.camera
    
    if not camera:
        print("No active camera found!")
        return
    
    font_objects = [obj for obj in scene.objects 
                   if obj.type == 'FONT' and obj.visible_get()]
    
    if not font_objects:
        print("No font objects found in scene!")
        return

    print(f"Scaling {len(font_objects)} font objects to {target_pixel_height} pixels:")
    
    for obj in font_objects:
        # Store original state and reset scale
        original_scale = obj.scale.copy()
        
        # Reset to uniform scale first
        obj.scale = (1, 1, 1)
        bpy.context.view_layer.update()
        
        # Get current pixel height
        current_pixel_height = get_font_pixel_height(camera, obj)
        
        if current_pixel_height > 0:
            # Calculate scale factor
            scale_factor = target_pixel_height / current_pixel_height
            
            # Apply scale uniformly
            obj.scale = (scale_factor, scale_factor, scale_factor)
            
            # Insert keyframe
            obj.keyframe_insert(data_path="scale")
            
            # Verify result
            bpy.context.view_layer.update()
            new_height = get_font_pixel_height(camera, obj)
            
            print(f"Frame {scene.frame_current}: '{obj.name}' - {current_pixel_height:.1f}px -> {new_height:.1f}px (scale: {scale_factor:.3f})")
        else:
            print(f"Frame {scene.frame_current}: '{obj.name}' - Zero height, skipping")
            
def get_object_camera_bounds(obj, camera):
    """
    Get the bounding box of an object in camera view space (0-1 range)
    Returns: (min_x, max_x, min_y, max_y, any_visible)
    """
    scene = bpy.context.scene
    
    # Get object bounding box in world coordinates
    bbox_world = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    
    # Project to camera view space (0-1 range)
    bbox_camera = []
    for point in bbox_world:
        co_2d = bpy_extras.object_utils.world_to_camera_view(scene, camera, point)
        bbox_camera.append(co_2d)
    
    if not bbox_camera:
        return 0, 0, 0, 0, False
    
    # Get min/max in view space
    min_x = min(p.x for p in bbox_camera)
    max_x = max(p.x for p in bbox_camera)
    min_y = min(p.y for p in bbox_camera)
    max_y = max(p.y for p in bbox_camera)
    
    # Check if any part is visible (within 0-1 range in both axes)
    any_visible = (
        (min_x < 1 and max_x > 0) and 
        (min_y < 1 and max_y > 0)
    )
    
    return min_x, max_x, min_y, max_y, any_visible

def analyze_font_visibility(obj):
    """
    Main function to analyze all font objects' visibility and positioning
    """
    
    outward_objects = []
    
    scene = bpy.context.scene
    camera = scene.camera
    
    if not camera:
        print("❌ No active camera found!")
        return
    
    min_x, max_x, min_y, max_y, is_visible = get_object_camera_bounds(obj, camera)
    
    # Analyze positioning
    completely_outside = not is_visible
    partially_outside = is_visible and (
        min_x < 0 or max_x > 1 or 
        min_y < 0 or max_y > 1
    )
    completely_inside = is_visible and not partially_outside
    
    # Calculate how much is outside borders
    outside_left = max(0, -min_x)
    outside_right = max(0, max_x - 1)
    outside_bottom = max(0, -min_y)
    outside_top = max(0, max_y - 1)
    
    # Determine status
    if completely_outside:
        return True

    elif partially_outside:
        return True

    else:
        return False


def create_animated_empty_parent(objects_list, empty_name="Empty_Parent", rotation_frames=(0, 23)):

    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.select_all(action='DESELECT')

    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
    empty_obj = bpy.context.active_object
    empty_obj.name = empty_name

    # Parent all objects to the empty
    for obj in objects_list:
        if obj and obj.type != 'EMPTY': 
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

            obj.parent = empty_obj

    add_z_rotation_animation(empty_obj, rotation_frames[0], rotation_frames[1])
    
    return empty_obj

def add_z_rotation_animation(obj, start_frame=0, end_frame=23):
    """
    Adds a 360-degree Z rotation animation to an object.
    
    Args:
        obj: The object to animate
        start_frame (int): Starting frame for animation
        end_frame (int): Ending frame for animation
    """
    
    # Ensure we're working with the correct object
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    # Set initial rotation at start frame
    bpy.context.scene.frame_set(start_frame)
    obj.rotation_euler = (0, 0, 0)  # 0 degrees Z rotation
    obj.keyframe_insert(data_path="rotation_euler", index=2)  # index=2 is Z axis
    
    # Set final rotation at end frame
    bpy.context.scene.frame_set(end_frame)
    obj.rotation_euler = (0, 0, radians(360))  # 360 degrees Z rotation
    obj.keyframe_insert(data_path="rotation_euler", index=2)
    
    # Set interpolation to linear for constant rotation speed
    if obj.animation_data and obj.animation_data.action:
        for fcurve in obj.animation_data.action.fcurves:
            if fcurve.data_path == "rotation_euler" and fcurve.array_index == 2:
                for keyframe in fcurve.keyframe_points:
                    keyframe.interpolation = 'LINEAR'


# ---------- helpers ----------
def _world_aabb(obj):
    deps = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(deps)
    try:
        me = obj_eval.to_mesh()
    except Exception:
        me = None
    if me and len(me.vertices) > 0:
        mw = obj.matrix_world
        xs = []; ys = []; zs = []
        for v in me.vertices:
            w = mw @ v.co
            xs.append(w.x); ys.append(w.y); zs.append(w.z)
        obj_eval.to_mesh_clear()
    else:
        xs = []; ys = []; zs = []
        for c in obj.bound_box:
            w = Vector(c)
            xs.append(w.x); ys.append(w.y); zs.append(w.z)
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)




def _edge_angle_in_camera(edge_dir_world, cam_right, cam_up, cam_fwd):
    proj = edge_dir_world - cam_fwd * edge_dir_world.dot(cam_fwd)
    if proj.length_squared == 0.0:
        return 0.0
    proj.normalize()
    x = proj.dot(cam_right); y = proj.dot(cam_up)
    return atan2(y, x)


def _nudge_toward_camera(pos, cam_fwd, amount):  # amount in world units
    return pos - cam_fwd * amount


def _add_poly_spline(curve, pts):
    sp = curve.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p.x, p.y, p.z, 1.0)
    return sp


def _parent_keep_world(child: bpy.types.Object, parent: bpy.types.Object):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def get_first_spline_midpoint(curve_obj):
    
    # Verify input is a curve
    if not curve_obj or curve_obj.type != 'CURVE':
        print("Error: Input is not a curve object")
        return None
    
    # Get curve data
    curve = curve_obj.data
    
    # Check if curve has splines
    if not curve.splines:
        print("Error: Curve has no splines")
        return None
    
    # Get the first spline
    spline = curve.splines[0]
    
    # Handle different spline types
    if spline.type == 'BEZIER':
        # For Bezier splines, use control points
        points = spline.bezier_points
        if len(points) == 0:
            return None
        
        # Calculate midpoint based on handle positions
        if len(points) == 1:
            # Single point - just return its position
            midpoint = points[0].co
        else:
            # Find middle point(s)
            mid_index = len(points) // 2
            if len(points) % 2 == 1:
                # Odd number of points - use middle point
                midpoint = points[mid_index].co
            else:
                # Even number of points - average two middle points
                midpoint = (points[mid_index-1].co + points[mid_index].co) / 2
    
    elif spline.type == 'POLY':
        # For poly splines, use points array
        points = spline.points
        if len(points) == 0:
            return None
        
        if len(points) == 1:
            midpoint = points[0].co
        else:
            mid_index = len(points) // 2
            if len(points) % 2 == 1:
                midpoint = points[mid_index].co
            else:
                midpoint = (points[mid_index-1].co + points[mid_index].co) / 2
    
    elif spline.type == 'NURBS':
        # For NURBS splines
        points = spline.points
        if len(points) == 0:
            return None
        
        if len(points) == 1:
            midpoint = points[0].co
        else:
            mid_index = len(points) // 2
            if len(points) % 2 == 1:
                midpoint = points[mid_index].co
            else:
                midpoint = (points[mid_index-1].co + points[mid_index].co) / 2
    else:
        print(f"Error: Unsupported spline type: {spline.type}")
        return None
    
    # Transform from local to world space
    world_midpoint = curve_obj.matrix_world @ midpoint
    
    return world_midpoint


# ---------- main ----------
def create_bracket_axes_with_text(
    obj_name: str,
    *,
    margin_ratio: float = 0.06,    # offset from bbox (fraction of diag)
    tick_len_ratio: float = 0.1,  # tick/elbow length (fraction of diag)
    bevel_depth: float = 0.001,   # line thickness (also for bbox)
    font_size: float = 0.2,
    decimals: int = 2,
    unit_suffix: str = "",        # e.g. '"' for inches
    ground_name: str | None = "Plane",  # name of your ground/floor object (None => world-Z up)
    clearance_ratio: float = 0.005      # how high to float above ground (fraction of diag)
):
    """
    Draws bracket/axis lines around an object and camera-facing dimension labels.
    Curves & text are guaranteed to sit *above* the ground plane to avoid z-fighting/hiding.
    """

    obj = bpy.data.objects.get(obj_name)
    if not obj:
        raise ValueError(f'Object "{obj_name}" not found.')

    # Camera info
    cam = bpy.context.scene.camera or next((o for o in bpy.context.scene.objects if o.type == 'CAMERA'), None)
    if cam is None:
        raise RuntimeError("No camera found.")
    cq = cam.matrix_world.to_quaternion()
    cam_right = cq @ Vector((1, 0, 0))
    cam_up    = cq @ Vector((0, 1, 0))
    cam_fwd   = cq @ Vector((0, 0, -1))  # camera looks along -Z


    ## save "Z" angle data and make "Z" to 0, and save previous z data in a veriable.
    z_copy = obj.rotation_euler.z
    obj.rotation_euler.z = 0

    # AABB
    min_x, max_x, min_y, max_y, min_z, max_z = _world_aabb(obj)
    len_x = max_x - min_x
    len_y = max_y - min_y
    len_z = max_z - min_z
    diag  = Vector((len_x, len_y, len_z)).length or 1.0  # avoid zero

    # Distances (kept your +0.11 additive)
    off   = margin_ratio * diag + 0.11
    tick  = tick_len_ratio * diag
    push  = 0.001 * diag

    # --- Ground-aware lift setup ---
    # Use ground object if given; else assume world-Z up through origin
    ground = bpy.data.objects.get(ground_name) if ground_name else None
    if ground:
        gq = ground.matrix_world.to_quaternion()
        ground_n = (gq @ Vector((0, 0, 1))).normalized()  # plane normal in world space
        ground_p = ground.matrix_world.translation         # a point on the plane
    else:
        ground_n = Vector((0, 0, 1))
        ground_p = Vector((0, 0, 0))

    clearance = clearance_ratio * diag  # how high (in world units) above ground to keep graphics

    def _above_ground(p: Vector) -> Vector:
        """Ensure p is at least `clearance` above (ground_p, ground_n)."""
        d = (p - ground_p).dot(ground_n)  # signed distance from plane
        if d < clearance:
            p = p + ground_n * (clearance - d)
        return p

    def _add_poly_spline_safe(cu, pts):
        """Lift above ground + small camera nudge to avoid coplanar artifacts with mesh."""
        pts2 = [_above_ground(_nudge_toward_camera(p, cam_fwd, push)) for p in pts]
        _add_poly_spline(cu, pts2)

    # Clean old objects
    to_delete = [
        f"AX_X_{obj.name}",
        f"AX_Z_R_{obj.name}", f"AX_Y_R_{obj.name}",
        f"AX_Z_L_{obj.name}", f"AX_Y_L_{obj.name}",
        f"AX_TX_X_{obj.name}",
        f"AX_TX_Y_R_{obj.name}", f"AX_TX_Y_L_{obj.name}",
        f"AX_TX_Z_R_{obj.name}", f"AX_TX_Z_L_{obj.name}",
        f"BB_{obj.name}",
    ]
    for n in to_delete:
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)

    # ------ helpers to make parented curves/text ------
    def upsert_curve(name):
        cu = bpy.data.curves.get(name + "_Curve") or bpy.data.curves.new(name + "_Curve", 'CURVE')
        cu.dimensions = '3D'; cu.resolution_u = 1
        while cu.splines:
            cu.splines.remove(cu.splines[0])
        ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, cu)
        if ob.name not in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.link(ob)
        ob.data = cu
        cu.bevel_depth = bevel_depth; cu.bevel_resolution = 1
        ob.show_in_front = True; ob.hide_render = False
        _parent_keep_world(ob, obj)  # parent bracket curve to object
        return ob, cu

    def upsert_text(name, body, loc, line_dir):
        t = bpy.data.objects.get(name)
        if not t or t.type != 'FONT':
            if t and t.type != 'FONT':
                bpy.data.objects.remove(t, do_unlink=True)
            cu = bpy.data.curves.new(name + "_Curve", 'FONT')
            cu.body = body
            t = bpy.data.objects.new(name, cu)
            bpy.context.scene.collection.objects.link(t)
        else:
            t.data.body = body

        # Keep text above ground and slightly toward camera
        t.location = _above_ground(_nudge_toward_camera(loc, cam_fwd, push))
        t.data.size = font_size
        t.data.align_x = 'LEFT'#'CENTER'
        t.data.align_y = 'TOP_BASELINE'#'CENTER'
        t.show_in_front = True
        t.hide_render = False
        _parent_keep_world(t, obj)  # parent text to object

        # --- text color setup ---
        mat_name = "TextBlack"
        mat = bpy.data.materials.get(mat_name)
        if not mat:
            mat = bpy.data.materials.new(mat_name)
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            out = mat.node_tree.nodes.get("Material Output")
            mat.node_tree.nodes.remove(bsdf)
            #if bsdf:
            #    bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)  # RGBA black
            rgb = mat.node_tree.nodes.new('ShaderNodeRGB')
            rgb.outputs[0].default_value = (0, 0, 0, 1)
            mat.node_tree.links.new(rgb.outputs[0], out.inputs[0])
        if len(t.data.materials) == 0:
            t.data.materials.append(mat)
        else:
            t.data.materials[0] = mat
        # -------------------------

        # Face camera
        for c in list(t.constraints):
            if c.type in {'DAMPED_TRACK', 'TRACK_TO', 'COPY_ROTATION'}:
                t.constraints.remove(c)
        dt = t.constraints.new('TRACK_TO')
        dt.target = cam
        dt.track_axis = 'TRACK_Z'
        # (UP axis defaults to UP_Y; adjust if needed)

        # optional roll alignment — compute angle of the line in camera plane
        angle = _edge_angle_in_camera(line_dir, cam_right, cam_up, cam_fwd)
        gname = name + "_Guide"
        e = bpy.data.objects.get(gname) or bpy.data.objects.new(gname, None)
        if e.name not in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.link(e)
        e.location = t.location
        e.rotation_euler = (0.0, 0.0, angle)
        try:
            print(e.type)
            e.empty_disply_size = 0.01
        except:
            pass
        e.hide_render = True
        e.hide_viewport = True
        _parent_keep_world(e, obj)
        

        return t

    # ------ build brackets (top X; Y/Z on BOTH sides) ------
        # ------ build brackets with square ends (top X; Y/Z on BOTH sides) ------
    #off = off/2
    
    #off *= 2
    
    top_y = max_y + off/2
    top_z = max_z + off/2
    right_x = max_x + off/2
    left_x = min_x - off/2
    front_y = max_y + off/2
    bottom_z = min_z - off

    # X (top) - Horizontal square bracket: |-----|
    x_obj, x_cu = upsert_curve(f"AX_X_{obj.name}")
    # Main horizontal line
    _add_poly_spline_safe(x_cu, [Vector((min_x- off/4, min_y, top_z)),
                                 Vector((max_x + off/4, min_y, top_z))])
    # Left vertical end
    _add_poly_spline_safe(x_cu, [Vector((min_x- off/4, min_y, top_z)),
                                 Vector((min_x- off/4, min_y, top_z - off/4))])
    # Right vertical end  
    _add_poly_spline_safe(x_cu, [Vector((max_x+ off/4, min_y, top_z)),
                                 Vector((max_x+ off/4, min_y, top_z - off/4))])
                                 
                                 
    # X (top 2) - Horizontal square bracket: |-----|
    x2_obj, x2_cu = upsert_curve(f"AX_X2_{obj.name}")
    # Main horizontal line
    _add_poly_spline_safe(x2_cu, [Vector((min_x- off/4, max_y, top_z)),
                                 Vector((max_x + off/4, max_y, top_z))])
    # Left vertical end
    _add_poly_spline_safe(x2_cu, [Vector((min_x- off/4, max_y, top_z)),
                                 Vector((min_x- off/4, max_y, top_z - off/4))])
    # Right vertical end  
    _add_poly_spline_safe(x2_cu, [Vector((max_x+ off/4, max_y, top_z)),
                                 Vector((max_x+ off/4, max_y, top_z - off/4))])                                 
                                 

    # Z right - Square bracket: ┌─] shape
    zR_obj, zR_cu = upsert_curve(f"AX_Z_R_{obj.name}")
    # Vertical line
    _add_poly_spline_safe(zR_cu, [Vector((right_x, min_y - off/4, bottom_z)),
                                  Vector((right_x, min_y - off/4, max_z + off/4))]) # + off))])
    # Top horizontal end
    _add_poly_spline_safe(zR_cu, [Vector((right_x, min_y - off/4, max_z+ off/4)), # + off)),
                                  Vector((right_x - off/4, min_y, max_z+ off/4))]) # + off))])
    # Bottom horizontal end
    _add_poly_spline_safe(zR_cu, [Vector((right_x, min_y - off/4, bottom_z)),
                                  Vector((right_x - off/4, min_y, bottom_z))])
                                  
    # Z2 right - Square bracket: ┌─] shape
    zR2_obj, zR2_cu = upsert_curve(f"AX_Z2_R_{obj.name}")
    # Vertical line
    _add_poly_spline_safe(zR2_cu, [Vector((right_x, max_y + off/4, bottom_z)),
                                  Vector((right_x, max_y + off/4, max_z + off/4))]) # + off))])
    # Top horizontal end
    _add_poly_spline_safe(zR2_cu, [Vector((right_x, max_y + off/4, max_z+ off/4)), # + off)),
                                  Vector((right_x - off/4, max_y, max_z+ off/4))]) # + off))])
    # Bottom horizontal end
    _add_poly_spline_safe(zR2_cu, [Vector((right_x, max_y + off/4, bottom_z)),
                                  Vector((right_x - off/4, max_y, bottom_z))])

    # Z left - Square bracket: [─┐ shape  
    zL_obj, zL_cu = upsert_curve(f"AX_Z_L_{obj.name}")
    # Vertical line
    _add_poly_spline_safe(zL_cu, [Vector((left_x, min_y - off/4, bottom_z)),
                                  Vector((left_x, min_y - off/4, max_z + off/4))]) # + off))])
    # Top horizontal end
    _add_poly_spline_safe(zL_cu, [Vector((left_x, min_y - off/4, max_z + off/4)), # + off)),
                                  Vector((left_x + off/4, min_y, max_z + off/4))]) # + off))])
    # Bottom horizontal end
    _add_poly_spline_safe(zL_cu, [Vector((left_x, min_y - off/4, bottom_z)),
                                  Vector((left_x + off/4, min_y, bottom_z))])
                                  
    
    # Z left - Square bracket: [─┐ shape  
    zL2_obj, zL2_cu = upsert_curve(f"AX_Z2_L_{obj.name}")
    # Vertical line
    _add_poly_spline_safe(zL2_cu, [Vector((left_x, max_y + off/4, bottom_z)),
                                  Vector((left_x, max_y + off/4, max_z + off/4))]) # + off))])
    # Top horizontal end
    _add_poly_spline_safe(zL2_cu, [Vector((left_x, max_y +  off/4, max_z + off/4)), # + off)),
                                  Vector((left_x + off/4, max_y , max_z + off/4))]) # + off))])
    # Bottom horizontal end
    _add_poly_spline_safe(zL2_cu, [Vector((left_x, max_y +  off/4, bottom_z)),
                                  Vector((left_x + off/4, max_y, bottom_z))])                              
    

    # Y right - Square bracket: |─] shape
    yR_obj, yR_cu = upsert_curve(f"AX_Y_R_{obj.name}")
    # Horizontal line
    _add_poly_spline_safe(yR_cu, [Vector((right_x, min_y, bottom_z)),
                                  Vector((right_x, max_y, bottom_z))])
    # Left vertical end
    _add_poly_spline_safe(yR_cu, [Vector((right_x, min_y, bottom_z)),
                                  Vector((right_x- off/4, min_y, bottom_z - off/2))])
    # Right vertical end
    _add_poly_spline_safe(yR_cu, [Vector((right_x, max_y, bottom_z)),
                                  Vector((right_x- off/4, max_y, bottom_z - off/2))])

    # Y left - Square bracket: [─| shape
    yL_obj, yL_cu = upsert_curve(f"AX_Y_L_{obj.name}")
    # Horizontal line
    _add_poly_spline_safe(yL_cu, [Vector((left_x, min_y, bottom_z)),
                                  Vector((left_x, max_y, bottom_z))])
    # Left vertical end
    _add_poly_spline_safe(yL_cu, [Vector((left_x, min_y, bottom_z)),
                                  Vector((left_x +  off/4, min_y, bottom_z + off/2))])
    # Right vertical end
    _add_poly_spline_safe(yL_cu, [Vector((left_x, max_y, bottom_z)),
                                  Vector((left_x +  off/4, max_y, bottom_z + off/2))])

    # ------ labels (midpoints) ------
    inches_mutiplier = 32.838
    loc = get_first_spline_midpoint(x_obj)
    loc = Vector([loc[0], loc[1], loc[2]])
    print("LOC:", loc)
    _tx = upsert_text(f"AX_TX_X_{obj.name}", f"   {int(len_x*inches_mutiplier)}{unit_suffix}   ",
                loc, Vector((1, 0, 0)))  #Vector(((min_x + max_x) * 0.5, min_y, top_z))
    
    loc = get_first_spline_midpoint(x2_obj)
    loc = Vector([loc[0], loc[1], loc[2]])
    _tx2 = upsert_text(f"AX_TX_X2_{obj.name}", f"   {int(len_x*inches_mutiplier)}{unit_suffix}   ",
                loc , Vector((1, 0, 0)))  #Vector(((min_x + max_x) * 0.5, max_y, top_z))

    loc = get_first_spline_midpoint(yR_obj)
    loc = Vector([loc[0], loc[1], loc[2]+0.02])
    _tyr = upsert_text(f"AX_TX_Y_R_{obj.name}", f"   {int(len_y*inches_mutiplier)}{unit_suffix}   ",
                loc , Vector((0, 1, 0)))  #Vector((right_x, (max_y + min_y) * 0.5, bottom_z))
                
    loc = get_first_spline_midpoint(yL_obj)
    loc = Vector([loc[0], loc[1], loc[2]+0.02])
    _tyl = upsert_text(f"AX_TX_Y_L_{obj.name}", f"   {int(len_y*inches_mutiplier)}{unit_suffix}   ",
                loc , Vector((0, 1, 0))) #Vector((left_x,  (max_y + min_y) * 0.5, bottom_z))
    
    loc = get_first_spline_midpoint(zR_obj)
    loc = Vector([loc[0], loc[1], loc[2]])
    _tzr = upsert_text(f"AX_TX_Z_R_{obj.name}", f"   {int(len_z*inches_mutiplier)}{unit_suffix}   ",
                loc , Vector((0, 0, 1)))  #Vector((right_x, min_y, (min_z + max_z) * 0.5))
                
    loc = get_first_spline_midpoint(zL_obj)
    loc = Vector([loc[0], loc[1], loc[2]])
    _tzl =upsert_text(f"AX_TX_Z_L_{obj.name}", f"   {int(len_z*inches_mutiplier)}{unit_suffix}   ",
                loc , Vector((0, 0, 1)))  #Vector((left_x,  min_y, (min_z + max_z) * 0.5))
    
    loc = get_first_spline_midpoint(zR2_obj)
    loc = Vector([loc[0], loc[1], loc[2]])
    _tzr2 = upsert_text(f"AX_TX_Z2_R_{obj.name}", f"   {int(len_z*inches_mutiplier)}{unit_suffix}   ",
                loc, Vector((0, 0, 1)))   #Vector((right_x, max_y, (min_z + max_z) * 0.5))
    
    loc = get_first_spline_midpoint(zL2_obj)
    loc = Vector([loc[0], loc[1], loc[2]])
    _tzl2 = upsert_text(f"AX_TX_Z2_L_{obj.name}", f"   {int(len_z*inches_mutiplier)}{unit_suffix}   ",
                loc , Vector((0, 0, 1))) #Vector((left_x,  max_y, (min_z + max_z) * 0.5))
    
    
    # revert rotation back to previous
    obj.rotation_euler.z = z_copy

    print(f'{obj.name} | X:{len_x:.{decimals}f}{unit_suffix}  '
          f'Y:{len_y:.{decimals}f}{unit_suffix}  Z:{len_z:.{decimals}f}{unit_suffix}')
    # --- text color setup ---
    line_mat_name = "LinesGray"
    line_mat = bpy.data.materials.get(line_mat_name)
    if not line_mat:
        line_mat = bpy.data.materials.new(line_mat_name)
        line_mat.use_nodes = True
        bsdf = line_mat.node_tree.nodes.get("Principled BSDF")
        out = line_mat.node_tree.nodes.get("Material Output")
        line_mat.node_tree.nodes.remove(bsdf)
        #if bsdf:
        #    bsdf.inputs["Base Color"].default_value = (0, 0, 0, 1)  # RGBA black
        rgb = line_mat.node_tree.nodes.new('ShaderNodeRGB')
        rgb.outputs[0].default_value = (0.076185, 0.102242, 0.124772,1)
        line_mat.node_tree.links.new(rgb.outputs[0], out.inputs[0])
            
    for ob in [x_obj, x2_obj, yR_obj, yL_obj, zR_obj, zR2_obj, zL_obj, zL2_obj]:
        ob.data.materials.append(line_mat)
    
    return {
        "curves": {"X": x_obj, "Y_right": yR_obj, "Y_left": yL_obj,
                   "Z_right": zR_obj, "Z_left": zL_obj, "X2": x2_obj, "Z_right_B": zR2_obj, "Z_left_B": zL2_obj},
        "dimensions": {"X": len_x, "Y": len_y, "Z": len_z},
        "texts": {"_tx": _tx, "_tx2":_tx2, "_tyr":_tyr, "_tyl":_tyl, "_tzr":_tzr, "_tzl":_tzl, "_tzr2":_tzr2, "_tzl2":_tzl2}
    }


def join_children_to_single(
    parent_name: str,
    *,
    new_name: str | None = None,
    recursive: bool = True,
    include_parent_mesh: bool = True,
    apply_modifiers: bool = False,     # apply each child’s modifiers before join
    preserve_originals: bool = False,  # join duplicates, keep originals untouched
    collapse_parent: bool = False      # delete empty parent after join
) -> bpy.types.Object:

    parent = bpy.data.objects.get(parent_name)
    if not parent:
        raise ValueError(f'Parent "{parent_name}" not found.')

    # Collect targets
    children = parent.children_recursive if recursive else parent.children
    targets = [c for c in children if c.type == 'MESH']
    if include_parent_mesh and parent.type == 'MESH':
        targets = [parent] + targets

    if len(targets) < 1:
        raise ValueError("No mesh objects found under the parent.")

    # Ensure Object mode
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')

    # Optionally duplicate to preserve originals
    if preserve_originals:
        dupes = []
        for ob in targets:
            d = ob.copy()
            d.data = ob.data.copy() if ob.data else None
            # Link to active collection so the join operator can see them
            bpy.context.collection.objects.link(d)
            d.matrix_world = ob.matrix_world.copy()
            dupes.append(d)
        targets = dupes

    # Optionally apply modifiers on each target (only safe on real objects, not instances)
    if apply_modifiers:
        for ob in targets:
            bpy.context.view_layer.objects.active = ob
            ob.select_set(True)
            # Apply all modifiers if possible
            for md in list(ob.modifiers):
                try:
                    bpy.ops.object.modifier_apply(modifier=md.name)
                except Exception:
                    pass
            ob.select_set(False)

    # Select all targets and join into the first
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for ob in targets:
        ob.select_set(True)

    active = targets[0]
    bpy.context.view_layer.objects.active = active

    bpy.ops.object.join()  # merges all selected meshes into 'active'

    # Rename the result
    result = bpy.context.view_layer.objects.active
    result.name = new_name or (parent.name + "_joined")
    if result.data:
        result.data.name = result.name + "_Mesh"

    # Optionally collapse the empty parent (leave only the joined mesh)
    if collapse_parent and parent != result and parent.type == 'EMPTY':
        # Reparent result to parent's parent while keeping world transform
        gp = parent.parent
        result.matrix_world = result.matrix_world.copy()
        result.parent = gp
        result.matrix_parent_inverse = (gp.matrix_world.inverted()
                                        if gp else Matrix.Identity(4))
        # Delete the empty parent
        bpy.data.objects.remove(parent, do_unlink=True)

    # Deselect everything, select only the result
    for o in bpy.context.selected_objects:
        o.select_set(False)
    result.select_set(True)
    bpy.context.view_layer.objects.active = result

    return result

def join_mesh_objects_except(excluded_names):
    """
    Selects all mesh objects except those with specified names and joins them.
    
    Args:
        excluded_names (list): List of object names to exclude from selection
        
    Returns:
        str: Name of the joined object, or None if no objects were joined
    """
    # Deselect all objects first
    bpy.ops.object.select_all(action='DESELECT')
    
    # Get all selectable mesh objects that are not in the excluded list
    mesh_objects = [
        obj for obj in bpy.context.selectable_objects 
        if obj.type == 'MESH' and obj.name not in excluded_names
    ]
    
    # Check if we have objects to join
    if len(mesh_objects) == 0:
        print("No mesh objects found to join (after exclusions)")
        return None
    
    if len(mesh_objects) == 1:
        print("Only one mesh object found, no joining needed")
        mesh_objects[0].select_set(True)
        bpy.context.view_layer.objects.active = mesh_objects[0]
        return mesh_objects[0].name
    
    # Select all the mesh objects we want to join
    for obj in mesh_objects:
        obj.select_set(True)
    
    # Set the first object as active (required for join operation)
    bpy.context.view_layer.objects.active = mesh_objects[0]
    
    # Store the name of the active object before joining
    original_active_name = mesh_objects[0].name
    
    # Join the objects
    bpy.ops.object.join()
    
    # The joined object is now the active object
    joined_object = bpy.context.active_object
    
    if joined_object:
        print(f"Successfully joined {len(mesh_objects)} objects into '{joined_object.name}'")
        return joined_object.name
    else:
        print("Failed to join objects")
        return None


# # Example:
excluded_objects = ['1_stage_1@899_layout', '1_bg_1@899_layout','1_stage_1@932_layout','1_bg_1@932_layout']
joined_object_name = join_mesh_objects_except(excluded_objects)
#bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')


main_model = bpy.data.objects.get(joined_object_name)
print(f"Joined object name: {joined_object_name}")

ground_name = '1_stage_1@899_layout'

resultant_objects = create_bracket_axes_with_text(
  joined_object_name,
  margin_ratio=0.00001,
  tick_len_ratio=0.01,
  bevel_depth=0.001,
  font_size=0.05,
  decimals=2,
  unit_suffix='"',
  ground_name=ground_name,          # change to your floor object name
  clearance_ratio=0.001         # raise/lower if needed
)


curves = resultant_objects["curves"] 
texts = resultant_objects["texts"] 

curve_obs = curves.values()
text_obs = texts.values()

rotation_empty = bpy.data.objects.get('__Main_Animation_Object__')
objects_to_parent = []
objects_to_parent.extend(curve_obs)
objects_to_parent.extend(text_obs)

for ob in objects_to_parent:
    ob.parent = rotation_empty
    
# UNIFORM FONT SIZE
cam = bpy.data.objects.get('__IMAGINE_RENDER_CAMERA__')

prev_fonts = set([f for f in bpy.data.fonts])
bpy.ops.font.open(filepath=FONT_PATH, relative_path=True)
now_fonts = set([f for f in bpy.data.fonts])

NEW_FONT = list(now_fonts - prev_fonts)[0]

for o in bpy.context.selectable_objects:
    if o.type == 'FONT':
        o.data.font = NEW_FONT
        
#        c = o.constraints.new('LIMIT_DISTANCE')
#        c.target = cam
#        c.distance = 2.8
#        c.limit_mode = 'LIMITDIST_ONSURFACE'




x_obj = curves['X']
_tx = texts['_tx']

x2_obj = curves['X2']
_tx2 = texts['_tx2']

yR_obj = curves['Y_right']    
_tyr = texts['_tyr']

yL_obj = curves['Y_left']
_tyl = texts['_tyl']

zR_obj = curves['Z_right']
_tzr = texts['_tzr']

zR2_obj= curves['Z_right_B']
_tzr2 = texts['_tzr2']

zL_obj = curves['Z_left']
_tzl = texts['_tzl']

zL2_obj = curves['Z_left_B']
_tzl2 = texts['_tzl2']



s_f = 0
e_f = 23
bpy.context.scene.frame_current = s_f


for f in range(s_f, e_f +1):
    objects_to_view = []
    bpy.context.scene.frame_current = f
    bpy.context.view_layer.update()
    if f < 6:
        objects_to_view = [x2_obj, _tx2, zR2_obj, _tzr2, yR_obj, _tyr]
        _tx2.data.align_x = 'CENTER'
        _tzr2.data.align_x = 'RIGHT'
        _tyr.data.align_x = 'RIGHT'
        if f>=4:
            _tzr2.data.align_x = 'LEFT'    
        _tx2.data.keyframe_insert(data_path="align_x")
        _tzr2.data.keyframe_insert(data_path="align_x")
        _tyr.data.keyframe_insert(data_path="align_x")
        
        checkout_ob = _tx2
        checkout_ob.data.align_y = 'TOP_BASELINE'
        checkout_ob.data.keyframe_insert(data_path="align_y")
        bpy.context.view_layer.update()
        is_outside_camera = analyze_font_visibility(checkout_ob)
        if is_outside_camera:
            checkout_ob.data.align_y = 'TOP'
        else:
            checkout_ob.data.align_y = 'TOP_BASELINE'
        print(f, checkout_ob.name, is_outside_camera, '<<FONT OUTSIDE FRAME STATUS')
        checkout_ob.data.keyframe_insert(data_path="align_y")

        
    elif 12 >= f >=6:
        objects_to_view = [x_obj, _tx, zR_obj, _tzr, yR_obj, _tyr]
        _tx.data.align_x = 'CENTER'
        _tzr.data.align_x = 'RIGHT'
        _tyr.data.align_x = 'RIGHT'
        

        if f>=9:
            _tzr.data.align_x = 'LEFT'
            _tyr.data.align_x = 'LEFT'
        _tzr.data.keyframe_insert(data_path="align_x")
        _tyr.data.keyframe_insert(data_path="align_x")
        _tx.data.keyframe_insert(data_path="align_x")
        
        checkout_ob = _tx
        checkout_ob.data.align_y = 'TOP_BASELINE'
        checkout_ob.data.keyframe_insert(data_path="align_y")
        bpy.context.view_layer.update()
        is_outside_camera = analyze_font_visibility(checkout_ob)
        if is_outside_camera:
            checkout_ob.data.align_y = 'TOP'
        else:
            checkout_ob.data.align_y = 'TOP_BASELINE'
        print(f, checkout_ob.name, is_outside_camera, '<<FONT OUTSIDE FRAME STATUS')
        checkout_ob.data.keyframe_insert(data_path="align_y")
        
    elif 18 > f >  12:
        objects_to_view = [x2_obj, _tx2, zL2_obj, _tzl2, yL_obj, _tyl]
        _tx2.data.align_x = 'CENTER' #'RIGHT'
        _tzl2.data.align_x = 'LEFT'
        _tyl.data.align_x = 'RIGHT'
        if f>=13:
            _tzl2.data.align_x = 'RIGHT'
        _tzl2.data.keyframe_insert(data_path="align_x")
        _tyl.data.keyframe_insert(data_path="align_x")
        _tx2.data.keyframe_insert(data_path="align_x")
        
        checkout_ob = _tx2
        checkout_ob.data.align_y = 'TOP_BASELINE'
        checkout_ob.data.keyframe_insert(data_path="align_y")
        bpy.context.view_layer.update()
        is_outside_camera = analyze_font_visibility(checkout_ob)
        
        if is_outside_camera:
            checkout_ob.data.align_y = 'TOP'
        else:
            checkout_ob.data.align_y = 'TOP_BASELINE'
        print(f, checkout_ob.name, is_outside_camera, '<<FONT OUTSIDE FRAME STATUS')
        checkout_ob.data.keyframe_insert(data_path="align_y")
        
        
        
    else:
        objects_to_view = [x_obj, _tx, zL_obj, _tzl, yL_obj, _tyl]
        _tyl.data.align_x = 'LEFT'
        _tyl.data.keyframe_insert(data_path="align_x")
        #if f>=20:
            
    bpy.context.view_layer.update()
    scale_font_objects_to_equal_height(target_pixel_height=25)
    bpy.context.view_layer.update()
            
    for o in objects_to_parent:
        if o in objects_to_view:
            o.hide_viewport = False
            o.hide_render = False
        else:
            o.hide_viewport = True
            o.hide_render = True
        o.keyframe_insert(data_path="hide_viewport")
        o.keyframe_insert(data_path="hide_render")
            

filepath = bpy.data.filepath
if not filepath:
    # Use current working directory and a default name for unsaved files
    dir = os.getcwd()
    name = "untitled"
else:
    name = filepath.split(os.sep)[-1].split('.blend')[0]
    dir = filepath.split(name)[0]
render_path = os.path.join(dir, name)
try:
    os.mkdir(render_path)
except:
    pass
bpy.context.scene.render.filepath = render_path + os.sep + 'Render'
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.image_settings.color_mode = 'RGBA'
bpy.context.scene.render.image_settings.color_depth = '8'
bpy.context.scene.render.image_settings.compression = 10

if excluded_objects:
    for obn in excluded_objects:
        print(obn)
        o = bpy.data.objects.get(obn)
        if o:
            o.hide_render = True
            o.hide_viewport = True

#main_model.hide_render = True
#main_model.hide_viewport = True
add_objects_to_holdout_collection(main_model, 'Holdout')
bpy.ops.render.render(animation = True)