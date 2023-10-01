bl_info = {
    'name': 'CopyCat',
    'author': 'Thierry Reding <thierry.reding@gmail.com>',
    'version': (1, 0, 1),
    'blender': (3, 4, 0),
    'description': '',
    'doc_url': 'https://',
    'category': 'Animation',
}

import os.path
import bpy, bpy_extras

class COPYCAT_BoneMapping(bpy.types.PropertyGroup):
    source: bpy.props.StringProperty(name = 'source', default = '', description = 'source bone')
    target: bpy.props.StringProperty(name = 'target', default = '', description = 'target bone')

class COPYCAT_BonesList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop_search(item, 'source', context.object.pose, 'bones', text = '', icon = 'BONE_DATA')
        layout.prop_search(item, 'target', context.object.pose, 'bones', text = '', icon = 'BONE_DATA')

class COPYCAT_ImportOperator(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = 'copycat.import'
    bl_label = 'Import FBX'

    files: bpy.props.CollectionProperty(type = bpy.types.OperatorFileListElement)
    directory: bpy.props.StringProperty(subtype = 'FILE_PATH')
    filename: bpy.props.StringProperty(subtype = 'FILE_PATH')

    filter_glob: bpy.props.StringProperty(default = '*.fbx', options = { 'HIDDEN' })

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return { 'RUNNING_MODAL' }

    def execute(self, context):
        armature = None

        for file in self.files:
            filepath = os.path.join(self.directory, file.name)
            filename, ext = os.path.splitext(file.name)

            bpy.ops.import_scene.fbx(filepath = filepath)

            # name action after filename
            action = context.object.animation_data.action
            action.name = filename

            # for multi-file imports, keep only the first armature object
            if not armature:
                armature = context.object
            else:
                bpy.ops.object.delete()

        context.view_layer.objects.active = armature
        armature.select_set(True)
        return { 'FINISHED' }

MAP_bones = (
    ('ik_foot_l',   'foot_l'),
    ('ik_foot_r',   'foot_r'),
    ('ik_hand_l',   'hand_l'),
    ('ik_hand_r',   'hand_r'),
    ('ik_hand_gun', 'hand_r'),
)

ENUM_ListOperation = [
    ('ADD', 'Add', 'Add'),
    ('REMOVE', 'Remove', 'Remove'),
    ('CLEAR', 'Clear', 'Clear'),
    ('DEFAULT', 'Default', 'Default')
]

class COPYCAT_ListOperator(bpy.types.Operator):
    bl_idname = 'copycat.list'
    bl_label = 'List Operator'
    bl_options = { 'UNDO' }

    operation: bpy.props.EnumProperty(items = ENUM_ListOperation)

    def execute(self, context):
        action = context.object.animation_data.action
        
        if self.operation == 'ADD':
            index = len(action.copycatMappings)
            item = action.copycatMappings.add()

            if index < 4:
                item.source = MAP_bones[index][0]
                item.target = MAP_bones[index][1]

            action.copycatIndex = index

        if self.operation == 'REMOVE':
            action.copycatMappings.remove(action.copycatIndex)
            if action.copycatIndex >= len(action.copycatMappings):
                action.copycatIndex = len(action.copycatMappings) - 1

        if self.operation == 'CLEAR':
            action.copycatMappings.clear()
            action.copycatIndex = 0

        if self.operation == 'DEFAULT':
            action.copycatMappings.clear()

            for source, target in MAP_bones:
                item = action.copycatMappings.add()
                item.source = source
                item.target = target

            action.copycatIndex = len(action.copycatMappings) - 1

        return { 'FINISHED' }

class COPYCAT_ApplyOperator(bpy.types.Operator):
    '''Tooltip'''
    bl_idname = 'copycat.apply'
    bl_label = 'Apply Constraint Transforms'
    bl_options = { 'UNDO' }

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        action = context.object.animation_data.action
        scene = context.scene
        obj = context.object
        mode = obj.mode

        # switch into pose mode so that bone constraints can be added
        bpy.ops.object.mode_set(mode = 'POSE')

        # add a copy transforms constraint for each bone mapping
        for mapping in action.copycatMappings:
            source = context.object.pose.bones[mapping.source]
            constraint = source.constraints.new('COPY_TRANSFORMS')
            constraint.target = context.object
            constraint.subtarget = mapping.target

        # restore object interaction mode
        bpy.ops.object.mode_set(mode = mode)

        return { 'FINISHED' }

class COPYCAT_ExportOperator(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    bl_idname = 'copycat.export'
    bl_label = 'Export FBX'

    filter_glob: bpy.props.StringProperty(default = '*.fbx', options = { 'HIDDEN' })
    filename_ext = '.fbx'

    def execute(self, context):
        bpy.ops.export_scene.fbx(filepath = self.filepath, use_selection = True, add_leaf_bones = False)

        return { 'FINISHED' }

class COPYCAT_Panel(bpy.types.Panel):
    bl_label = 'CopyCat'
    bl_idname = 'copycat_panel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Animation'

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        self.layout.operator('copycat.import', text = 'Import FBX', icon = 'IMPORT')

        if context.object and context.object.type == 'ARMATURE':
            action = context.object.animation_data.action

            row = self.layout.row(align = True)
            row.alignment = 'LEFT'

            col = row.column(align = True)
            col.template_list('COPYCAT_BonesList', '', action, 'copycatMappings', action, 'copycatIndex')

            col = row.column(align = True)
            op = col.operator(operator = 'copycat.list', text = '', icon = 'ADD')
            op.operation = 'ADD'
            op = col.operator(operator = 'copycat.list', text = '', icon = 'REMOVE')
            op.operation = 'REMOVE'
            op = col.operator(operator = 'copycat.list', text = '', icon = 'TRASH')
            op.operation = 'CLEAR'

            col.separator()

            op = col.operator(operator = 'copycat.list', text = '', icon = 'GROUP_BONE')
            op.operation = 'DEFAULT'

            if action.copycatMappings:
                self.layout.operator(operator = 'copycat.apply', text = 'Apply Bone Constraints', icon = 'CONSTRAINT')

            self.layout.operator(operator = 'copycat.export', icon = 'EXPORT')

classes = [
    COPYCAT_BoneMapping,
    COPYCAT_BonesList,
    COPYCAT_ImportOperator,
    COPYCAT_ListOperator,
    COPYCAT_ApplyOperator,
    COPYCAT_ExportOperator,
    COPYCAT_Panel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Action.copycatIndex = bpy.props.IntProperty()
    bpy.types.Action.copycatMappings = bpy.props.CollectionProperty(type = COPYCAT_BoneMapping)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Action.copycatMappings
    del bpy.types.Action.copycatIndex

if __name__ == '__main__':
    register()
