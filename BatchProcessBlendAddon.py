bl_info = {
    "name": "Batch Process on Blends",
    "blender": (3, 0, 0),
    "category": "Object",
    "author": "Suvigya Mishra",
    "description": "Runs python scripts on blend files of a directory in batch."
}

import bpy
import subprocess, os
from bpy.props import StringProperty, IntProperty, CollectionProperty
from bpy.types import PropertyGroup, Operator, Panel

class ScriptPath(PropertyGroup):
    path: StringProperty(name="Python Script Path", subtype='FILE_PATH')

class BatchProcessProperties(bpy.types.PropertyGroup):
    blends_directory: StringProperty(
        name="Blends Directory",
        subtype='DIR_PATH',
        description="Directory containing .blend files",
        default = '/Users/me/Downloads/',
    )

    number_of_scripts: IntProperty(
        name="Number of Scripts",
        default=1,
        min=1,
        description="Number of Python scripts to use",
        update = lambda self, context: update_script_paths(self, context)
    )

    script_paths: CollectionProperty(type=ScriptPath)



def update_script_paths(self, context):
    props = context.scene.batch_process_props
    target_count = props.number_of_scripts

    # Adjust the collection size
    while len(props.script_paths) < target_count:
        props.script_paths.add()
        props.script_paths[len(props.script_paths) - 1] = props.blend_directory
    while len(props.script_paths) > target_count:
        props.script_paths.remove(len(props.script_paths) - 1)
    
    # Ensure all paths are absolute
    for script_path in props.script_paths:
        if script_path.path:
            script_path.path = os.path.abspath(bpy.path.abspath(script_path.path))


class RunBatchProcessOperator(Operator):
    bl_idname = "batch_process.run"
    bl_label = "Run Batch Process"

    def execute(self, context):
        props = context.scene.batch_process_props
        blend_directory = props.blends_directory
        script_paths = [sp.path for sp in props.script_paths]

        blender_exec_path = bpy.app.binary_path
        
        for blend_file in os.listdir(blend_directory):
            if blend_file.endswith(".blend"):
                blend_path = os.path.join(blend_directory, blend_file)
                command = [f"{blender_exec_path}", f"{blend_path}", "--background", "--verbose", '2']

                for script in script_paths:
                    command.extend(["--python", f"{script}"])
                print(command)
                subprocess.run(command, check=True)
                '''
                try:
                    subprocess.run(command, check=True)
                except subprocess.CalledProcessError as e:
                    self.report({"ERROR"}, f"Error processing {blend_file}: {e}")'''

        self.report({"INFO"}, "Batch process completed.")
        return {'FINISHED'}

class BATCHPROCESS_PT_Panel(Panel):
    bl_idname = "BATCHPROCESS_PT_panel"
    bl_label = "Batch Process"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Batch Process'

    def draw(self, context):
        layout = self.layout
        props = context.scene.batch_process_props

        layout.prop(props, "blends_directory")
        layout.prop(props, "number_of_scripts")
        #layout.operator("batch_process.add_script_paths")
        

        for script in props.script_paths:
            layout.prop(script, "path")

        layout.operator("batch_process.run")

def register():
    bpy.utils.register_class(ScriptPath)
    bpy.utils.register_class(BatchProcessProperties)
    bpy.utils.register_class(RunBatchProcessOperator)
    bpy.utils.register_class(BATCHPROCESS_PT_Panel)

    bpy.types.Scene.batch_process_props = bpy.props.PointerProperty(type=BatchProcessProperties)

def unregister():
    bpy.utils.unregister_class(ScriptPath)
    bpy.utils.unregister_class(BatchProcessProperties)
    bpy.utils.unregister_class(RunBatchProcessOperator)
    bpy.utils.unregister_class(BATCHPROCESS_PT_Panel)

    del bpy.types.Scene.batch_process_props

if __name__ == "__main__":
    register()
