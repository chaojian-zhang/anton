import bpy
import numpy as np
import os
from scipy.spatial import ConvexHull

class Anton_OT_ForceUpdater(bpy.types.Operator):
    bl_idname = "anton.forceupdate"
    bl_label = ""

    diffuse_library = [
                        (255/255, 0/255, 199/255, 1),
                        (255/255, 248/255, 0/255, 1),
                        (83/255, 255/255, 0/255, 1),
                        (13/255, 218/255, 134/255, 1),
                        (115/255, 255/255, 0/255, 1),
                        (0/255, 217/255, 255/255, 1),
                        (235/255, 255/255, 0/255, 1),
                        (255/255, 178/255, 83/255, 1),
                        (148/255, 13/255, 88/255, 1),
                        (255/255, 0/255, 141/255, 1),
                        (255/255, 139/255, 0/255, 1)]

    def execute(self, context):
        scene = context.scene
        active_object = bpy.context.active_object

        if scene.anton.initialized:
            if 'NATIVE' not in bpy.data.materials:
                native_mat = bpy.data.materials.new(name='NATIVE')
                active_object.data.materials.append(native_mat)

            if 'FIXED' not in bpy.data.materials:
                mat = bpy.data.materials.new(name='FIXED')
                mat.diffuse_color = (1, 0, 0, 1)
                active_object.data.materials.append(mat)

            if 'NODESIGNSPACE' not in bpy.data.materials:
                nds_mat = bpy.data.materials.new(name='NODESIGNSPACE')
                nds_mat.diffuse_color = (0, 0, 1, 1)
                active_object.data.materials.append(nds_mat)

            for i in range(scene.anton.number_of_forces):
                if str('FORCE_{}'.format(i+1)) not in bpy.data.materials:

                    #TAKE CARE OF POPPING EXCESS FORCES
                    size = len(scene.forceprop)
                    new = scene.forceprop.add()
                    new.name = str(size+1)
                    new.direction_boolean = False
                    
                    temp_mat = bpy.data.materials.new(name='FORCE_{}'.format(i+1))
                    temp_mat.diffuse_color = self.diffuse_library[i]
                    active_object.data.materials.append(temp_mat)

                    bpy.ops.object.vertex_group_add()
                    active_object.vertex_groups.active.name = 'DIRECTION_{}'.format(i+1)

            scene.anton.forced = True
            self.report({'INFO'}, 'FORCES: {}'.format(scene.anton.number_of_forces))
            return{'FINISHED'}

        else:
            self.report({'ERROR'}, 'Initialize before force definition.')
            return{'CANCELLED'}

class Anton_OT_Initializer(bpy.types.Operator):
    bl_idname = 'anton.initialize'
    bl_label = 'Anton_Initializer'
    bl_description = 'Makes fixed materials and force vertex groups.'

    def execute(self, context):
        scene = context.scene
        active_object = bpy.context.active_object
        bpy.context.space_data.shading.type = 'MATERIAL'

        if not scene.anton.defined:
            if scene.anton.mode == 'HULL':

                objects = list()
                points = list()

                bound_scale = 1.25

                for _obj in bpy.data.objects:
                    dim = np.array([_obj.dimensions[0], _obj.dimensions[1], _obj.dimensions[2]])
                    if np.linalg.norm(dim) > 0:
                        if _obj.name_full != active_object.name_full:
                            objects.append(_obj)

                        theta = _obj.rotation_euler[0]
                        alpha = _obj.rotation_euler[1]
                        beta = _obj.rotation_euler[2]

                        rot_x = np.array([[1, 0, 0], [0, np.cos(theta), -1*np.sin(theta)], [0, np.sin(theta), np.cos(theta)]])
                        rot_y = np.array([[np.cos(alpha), 0, np.sin(alpha)], [0, 1, 0], [-1*np.sin(alpha), 0, np.cos(alpha)]])
                        rot_z = np.array([[np.cos(beta), -1*np.sin(beta), 0], [np.sin(beta), np.cos(beta), 0], [0, 0, 1]])

                        _rotational_matrix = np.matmul(np.matmul(rot_x, rot_y), rot_z)

                        for _vert in _obj.bound_box:
                            _scaled_bound = bound_scale * np.array([_obj.scale[0] * _vert[0], _obj.scale[1] * _vert[1], _obj.scale[2] * _vert[2]])
                            temp = _scaled_bound + np.array([_obj.location[0], _obj.location[1], _obj.location[2]])
                            _rotated_bound = np.matmul(_rotational_matrix, temp.T).T
                            points.append(_rotated_bound)

                hull = ConvexHull(points)
                points = np.array(points)

                with open(os.path.join(scene.anton.workspace_path, 'hull.stl'), 'w') as f:
                    f.write('GENERATED BY ANTON\n')
                    for _face in hull.simplices:
                        _a = points[_face][1] - points[_face][0]
                        _b = points[_face][2] - points[_face][0]
                        _cross_product = np.cross(_a, _b)
                        _normal = 1.0/np.linalg.norm(_cross_product) * _cross_product

                        f.write('facet normal {} {} {}\n'.format(
                                                                _normal[0],
                                                                _normal[1],
                                                                _normal[2]))
                        f.write('outer loop\n')
                        for i in range(3):
                            f.write('vertex {} {} {}\n'.format(
                                                                points[_face][i][0],
                                                                points[_face][i][1],
                                                                points[_face][i][2]))

                        f.write('endloop\n')
                        f.write('endfacet\n')

                    f.write('endsolid\n')
                
                active_object.select_set(True)

                for _obj in objects:
                    u_bool_mod = bpy.ops.object.modifier_add(type='BOOLEAN')
                    bpy.context.object.modifiers["Boolean"].operation = 'UNION'
                    bpy.context.object.modifiers["Boolean"].object = _obj
                    bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Boolean")

                    bpy.ops.object.select_all(action='DESELECT')
                    _obj.select_set(True)
                    bpy.ops.object.delete()

                    active_object.select_set(True)
                
                scene.anton.filename = active_object.name

                bpy.ops.import_mesh.stl(filepath=os.path.join(scene.anton.workspace_path, 'hull.stl'))    
                bound_object = bpy.context.object

                s_bool_mod = bpy.ops.object.modifier_add(type='BOOLEAN')
                bpy.context.object.modifiers["Boolean"].operation = 'DIFFERENCE'
                bpy.context.object.modifiers["Boolean"].object = active_object
                bpy.ops.object.modifier_apply(apply_as='DATA', modifier="Boolean")       

                bpy.ops.object.select_all(action='DESELECT')
                active_object.select_set(True)
                bpy.ops.object.delete()

                bpy.ops.export_mesh.stl(filepath=os.path.join(scene.anton.workspace_path, scene.anton.filename + '.stl'), ascii=True)
                active_object = bpy.context.active_object
                active_object.select_set(True)
                bpy.ops.object.delete()

                bpy.ops.import_mesh.stl(filepath=os.path.join(scene.anton.workspace_path, scene.anton.filename + '.stl'))      

            else:
                scene.anton.filename = active_object.name

                bpy.ops.export_mesh.stl(filepath=os.path.join(scene.anton.workspace_path, scene.anton.filename + '.stl'), ascii=True)
                active_object.select_set(True)
                bpy.ops.object.delete()

                bpy.ops.import_mesh.stl(filepath=os.path.join(scene.anton.workspace_path, scene.anton.filename + '.stl'))

            active_object = bpy.context.active_object
            
            scene.anton.initialized = True
            self.report({'INFO'}, 'Mode: {}, Material: {}'.format(
                                                                scene.anton.mode,
                                                                scene.anton.material))
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, 'Problem has been defined. In order to re-initialize, kindly restart the process.')
            return {'CANCELLED'}