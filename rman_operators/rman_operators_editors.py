from bpy.props import (StringProperty, BoolProperty, EnumProperty, IntProperty)

from ..rman_ui.rman_ui_base import CollectionPanel   
from ..rman_utils.draw_utils import _draw_ui_from_rman_config  
from ..rman_utils import scene_utils
from ..rman_utils import shadergraph_utils
from ..rman_render import RmanRender       
from .. import rfb_icons
from ..rman_operators.rman_operators_collections import return_empty_list     
import bpy
import re

class RENDERMAN_UL_LightLink_Light_List(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        rm = context.scene.renderman
        op = layout.operator("renderman.remove_light_link", text='', icon='REMOVE') 
        op.group_index = index
        light = item.light_ob
        light_shader = shadergraph_utils.get_light_node(light)      
        icon = rfb_icons.get_light_icon(light_shader.bl_label)        
        label = light.name
        layout.label(text=label, icon_value=icon.icon_id)     

class RENDERMAN_UL_LightLink_Object_List(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        rm = context.scene.renderman
        custom_icon = 'OBJECT_DATAMODE'
        layout.context_pointer_set("selected_obj", item.ob_pointer)
        op = layout.operator('renderman.remove_light_link_object', text='', icon='REMOVE')    
        label = item.ob_pointer.name
        layout.label(text=label, icon=custom_icon)

class RENDERMAN_UL_Object_Group_List(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        custom_icon = 'OBJECT_DATAMODE'
        layout.context_pointer_set("selected_obj", item.ob_pointer)
        op = layout.operator('renderman.remove_from_group', text='', icon='REMOVE')     
        label = item.ob_pointer.name
        layout.label(text=label, icon=custom_icon)  

class RENDERMAN_UL_LightMixer_Group_Members_List(bpy.types.UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        rm = context.scene.renderman
        light = item.light_ob
        op = layout.operator('renderman.remove_light_from_light_mixer_group', text='', icon='REMOVE')
   
        light_shader = shadergraph_utils.get_light_node(light)
        if not light_shader:
            layout.label(text=light.name)
            layout.prop('NO LIGHT SHADER')
            return 

        icon = rfb_icons.get_light_icon(light_shader.bl_label)
        layout.context_pointer_set("selected_light", item.light_ob)
        op.group_index = rm.light_mixer_groups_index
        layout.label(text=light.name, icon_value=icon.icon_id)

        light_rm = shadergraph_utils.get_rman_light_properties_group(light)
        if light_shader.bl_label == 'PxrEnvDayLight':
            layout.prop(light_shader, 'skyTint', text='')
        else:
            layout.prop(light_shader, 'enableTemperature', text='Temp')
            if light_shader.enableTemperature:
                layout.prop(light_shader, 'temperature', text='', slider=True)
            else:
                layout.prop(light_shader, 'lightColor', text='')
        layout.prop(light_shader, 'intensity', slider=True)
        layout.prop(light_shader, 'exposure', slider=True)        
        solo_icon = 'LIGHT'        
        if light.renderman.solo:
            solo_icon = 'OUTLINER_OB_LIGHT'
        layout.prop(light.renderman, 'solo', text='', icon=solo_icon, icon_only=True, emboss=False )
        mute_icon = 'HIDE_OFF'
        if light.renderman.mute:
            mute_icon = 'HIDE_ON'
        layout.prop(light.renderman, 'mute', text='', icon=mute_icon, icon_only=True, emboss=False)

class RENDER_OT_Renderman_Open_Workspace(bpy.types.Operator):

    bl_idname = "scene.rman_open_workspace"
    bl_label = "RenderMan Workspace"

    def execute(self, context):
        return{'FINISHED'}         

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False

        if context.scene.render.engine != "PRMAN_RENDER":
            return

        layout = self.layout
        rd = context.scene.render
        rm = context.scene.renderman
        rman_render = RmanRender.get_rman_render()
        is_rman_interactive_running = rman_render.rman_interactive_running

        split = layout.split(factor=0.33)
        col = layout.column()
        col.enabled = not is_rman_interactive_running

        _draw_ui_from_rman_config('rman_properties_scene', 'RENDER_PT_renderman_workspace', context, layout, rm) 

    def invoke(self, context, event):

        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=600)                      

class PRMAN_OT_Renderman_Open_Light_Mixer_Editor(CollectionPanel, bpy.types.Operator):

    bl_idname = "scene.rman_open_light_mixer_editor"
    bl_label = "RenderMan Light Mixer Editor"

    def light_list_items(self, context):
        pattern = re.compile(self.light_search_filter)   
        scene = context.scene
        rm = scene.renderman

        if self.do_light_filter and self.light_search_filter == '':
            return return_empty_list(label='No Lights Found')

        group_index = rm.light_mixer_groups_index
        lights_in_group = []
        object_groups = rm.light_mixer_groups
        object_group = object_groups[group_index]
        lights_in_group = [member.light_ob.name for member in object_group.members]        

        items = []
        for light in scene_utils.get_all_lights(context.scene, include_light_filters=False):
            if light.name not in lights_in_group:
                if self.do_light_filter and not re.match(pattern, light.name):
                    continue
                items.append((light.name, light.name, ''))
        if not items:
            return return_empty_list(label='No Lights Found') 
        elif self.do_light_filter:
            items.insert(0, ('0', 'Results (%d)' % len(items), '', '', 0))
        else:
            items.insert(0, ('0', 'Select Light', '', '', 0))                  
        return items

    def update_do_light_filter(self, context):
        self.selected_light_name = '0'

    selected_light_name: EnumProperty(name="Light", items=light_list_items)
    light_search_filter: StringProperty(name="Light Filter Search", default="")
    do_light_filter: BoolProperty(name="Filter", 
                                description="Search and add multiple lights",
                                default=False,
                                update=update_do_light_filter)    

    def execute(self, context):
        return{'FINISHED'}         

    def invoke(self, context, event):

        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=600)         

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        rm = scene.renderman
        self._draw_collection(context, layout, rm, "Light Mixer Groups",
                              "collection.add_remove",
                              "scene.renderman",
                              "light_mixer_groups", "light_mixer_groups_index", 
                              default_name='mixerGroup_%d' % len(rm.light_mixer_groups))

    def draw_item(self, layout, context, item):
        scene = context.scene
        rm = scene.renderman
        light_group = rm.light_mixer_groups[rm.light_mixer_groups_index]

        lights = [member.light_ob for member in light_group.members]
        row = layout.row(align=True)
        row.separator()        

        box = layout.box()
        row = box.row()
        split = row.split(factor=0.25)
        row = split.row()
        row.prop(self, 'do_light_filter', text='', icon='FILTER', icon_only=True)
        if not self.do_light_filter:
            row.prop(self, 'selected_light_name', text='')
            col = row.column()            
            if self.selected_light_name == '0' or self.selected_light_name == '':
                col.enabled = False
                op = col.operator("renderman.add_light_to_light_mixer_group", text='', icon='ADD')
            else:
                col.context_pointer_set('op_ptr', self) 
                col.context_pointer_set('selected_light', bpy.data.objects[self.selected_light_name])
                op = col.operator("renderman.add_light_to_light_mixer_group", text='', icon='ADD')
                op.do_scene_selected = False
        else:
            row.prop(self, 'light_search_filter', text='', icon='VIEWZOOM')
            row = box.row()
            split = row.split(factor=0.25)
            row = split.row()
            row.prop(self, 'selected_light_name', text='')
            col = row.column()
            if self.selected_light_name == '0' or self.selected_light_name == '':
                col.enabled = False
                op = col.operator("renderman.add_light_to_light_mixer_group", text='', icon='ADD')
            else:
                col.context_pointer_set('op_ptr', self) 
                col.context_pointer_set('selected_light', bpy.data.objects[self.selected_light_name])
                op = col.operator("renderman.add_light_to_light_mixer_group", text='', icon='ADD')
                op.do_scene_selected = False
        row = layout.row()
        split = row.split(factor=0.25)
        op = split.operator('renderman.convert_mixer_group_to_light_group', text='Convert to Light Group')
        op.group_index = rm.light_mixer_groups_index

        layout.template_list("RENDERMAN_UL_LightMixer_Group_Members_List", "Renderman_light_mixer_list",
                            light_group, "members", light_group, 'members_index', rows=6)

class PRMAN_PT_Renderman_Open_Light_Linking(bpy.types.Operator):

    bl_idname = "scene.rman_open_light_linking"
    bl_label = "RenderMan Light Linking Editor"

    def light_list_items(self, context):
        pattern = re.compile(self.light_search_filter)        
        scene = context.scene
        rm = scene.renderman
        if self.do_light_filter and self.light_search_filter == '':
            return return_empty_list(label='No Lights Found')
        
        lights_in_group = []
        for lg in rm.light_links:
            lights_in_group.append(lg.light_ob.name)

        items = []
        light_items = list()
        lightfilter_items = list()

        for light in scene_utils.get_all_lights(context.scene, include_light_filters=True):
            light_props = shadergraph_utils.get_rman_light_properties_group(light)            
            is_light = (light_props.renderman_light_role == 'RMAN_LIGHT')            
            if light.name not in lights_in_group:
                if self.do_light_filter and not re.match(pattern, light.name):
                    continue    
                if is_light:
                    light_items.append((light.name, light.name, '',))
                else:
                    lightfilter_items.append((light.name, light.name, ''))        
        if light_items:            
            items.extend(light_items)
        if lightfilter_items:           
            items.extend(lightfilter_items)
        if not items:
            return return_empty_list(label='No Lights Found') 
        elif self.do_light_filter:
            items.insert(0, ('0', 'Results (%d)' % len(items), '', '', 0))
        else:
            items.insert(0, ('0', 'Select Light', '', '', 0))                  
        return items    

    def update_do_light_filter(self, context):
        self.selected_light_name = '0'

    def obj_list_items(self, context):
        pattern = re.compile(self.object_search_filter)
        scene = context.scene
        rm = scene.renderman

        if self.do_object_filter and self.object_search_filter == '':
            return return_empty_list(label='No Objects Found')        

        group = rm.light_links[rm.light_links_index]

        objs_in_group = []
        for member in group.members:
            objs_in_group.append(member.ob_pointer.name)

        items = []
        for ob in [ob for ob in context.scene.objects if ob.type not in ['LIGHT', 'CAMERA']]:   
            if shadergraph_utils.is_mesh_light(ob):
                continue
            ob_name = ob.name   
            if ob_name not in objs_in_group:
                if self.do_object_filter and not re.match(pattern, ob_name):
                    continue  
                items.append((ob_name, ob_name, ''))
        if not items:
            return return_empty_list(label='No Objects Found')               
        elif self.do_object_filter:
            items.insert(0, ('0', 'Results (%d)' % len(items), '', '', 0))
        else:
            items.insert(0, ('0', 'Select Object', '', '', 0))
        return items       

    def update_do_object_filter(self, context):
        self.selected_obj_name = '0'

    light_search_filter: StringProperty(name="Light Filter Search", default="")
    do_light_filter: BoolProperty(name="Filter", 
                                description="Search and add multiple lights",
                                default=False, update=update_do_light_filter)
    selected_light_name: EnumProperty(name="", items=light_list_items)

    do_object_filter: BoolProperty(name="Object Filter", 
                                description="Search and add multiple objects",
                                default=False,
                                update=update_do_object_filter)    

    object_search_filter: StringProperty(name="Object Filter Search", default="")        

    selected_obj_name: EnumProperty(name="", items=obj_list_items)                   

    def execute(self, context):
        return{'FINISHED'}         

    def draw(self, context):
        layout = self.layout        
        scene = context.scene
        rm = scene.renderman
        row = layout.row()

        flow = row.column_flow(columns=3)
        row = flow.row()
        row.prop(self, 'do_light_filter', text='', icon='FILTER', icon_only=True)
        if not self.do_light_filter:
            row.prop(self, 'selected_light_name', text='')
            col = row.column()            
            if self.selected_light_name == '0' or self.selected_light_name == '':
                col.enabled = False                
                op = col.operator("renderman.add_light_link", text='', icon='ADD')
            else:
                col.context_pointer_set('op_ptr', self) 
                col.context_pointer_set('selected_light', bpy.data.objects[self.selected_light_name])
                op = col.operator("renderman.add_light_link", text='', icon='ADD')
        else:
            row.prop(self, 'light_search_filter', text='', icon='VIEWZOOM')  
            row = layout.row()             
            flow = row.column_flow(columns=3)
            row = flow.row()

            row.prop(self, 'selected_light_name', text='')
            col = row.column()
            if self.selected_light_name == '0' or self.selected_light_name == '':
                col.enabled= False
                op = col.operator("renderman.add_light_link", text='', icon='ADD')
            else:
                col.context_pointer_set('op_ptr', self) 
                col.context_pointer_set('selected_light', bpy.data.objects[self.selected_light_name])
                op = col.operator("renderman.add_light_link", text='', icon='ADD')

        flow.label(text='')

        row = layout.row()
        flow = row.column_flow(columns=3)

        flow.label(text='Lights')
        flow.label(text='Objects')
        flow.label(text='Illumination')

        row = layout.row()
        flow = row.column_flow(columns=3)

        flow.template_list("RENDERMAN_UL_LightLink_Light_List", "Renderman_light_link_list",
                            scene.renderman, "light_links", rm, 'light_links_index', rows=6)

        if rm.light_links_index != -1:
            light_link_item = scene.renderman.light_links[rm.light_links_index]  
            row = flow.row()   
            light_props = shadergraph_utils.get_rman_light_properties_group(light_link_item.light_ob)
            is_rman_light = (light_props.renderman_light_role == 'RMAN_LIGHT')
            row.prop(self, 'do_object_filter', text='', icon='FILTER', icon_only=True)
            if not self.do_object_filter:
                row.prop(self, 'selected_obj_name', text='')
                col = row.column()
                if self.selected_obj_name == '0' or self.selected_obj_name == '':
                    col.enabled = False
                    op = col.operator("renderman.add_light_link_object", text='', icon='ADD')                    
                else:
                    col.context_pointer_set('op_ptr', self) 
                    col.context_pointer_set('selected_obj', scene.objects[self.selected_obj_name])
                    op = col.operator("renderman.add_light_link_object", text='', icon='ADD')
                    op.do_scene_selected = False

                flow.template_list("RENDERMAN_UL_LightLink_Object_List", "Renderman_light_link_list",
                                light_link_item, "members", light_link_item, 'members_index', rows=5)            
            else:
                row.prop(self, 'object_search_filter', text='', icon='VIEWZOOM')
                row = flow.row()  
                row.prop(self, 'selected_obj_name')
                col = row.column()                
                if self.selected_obj_name == '0' or self.selected_obj_name == '':
                    col.enabled = False                    
                    op = col.operator("renderman.add_light_link_object", text='', icon='ADD')                
                else:
                    col.context_pointer_set('op_ptr', self) 
                    col.context_pointer_set('selected_obj', scene.objects[self.selected_obj_name])
                    op = col.operator("renderman.add_light_link_object", text='', icon='ADD')     
                    op.do_scene_selected = False           

                flow.template_list("RENDERMAN_UL_LightLink_Object_List", "Renderman_light_link_list",
                                light_link_item, "members", light_link_item, 'members_index', rows=4)                                          
      
            col = flow.column()
            if is_rman_light and len(light_link_item.members) > 0:
                col.prop(light_link_item, 'illuminate', text='')          

    def invoke(self, context, event):

        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=900)       

class PRMAN_OT_Renderman_Open_Groups_Editor(CollectionPanel, bpy.types.Operator):

    bl_idname = "scene.rman_open_groups_editor"
    bl_label = "RenderMan Trace Sets Editor"

    def obj_list_items(self, context):
        pattern = re.compile(self.object_search_filter)        
        scene = context.scene
        rm = scene.renderman

        if self.do_object_filter and self.object_search_filter == '':
            return return_empty_list(label='No Objects Found')        

        group = rm.object_groups[rm.object_groups_index]
        objs_in_group = []
        for member in group.members:
            objs_in_group.append(member.ob_pointer.name)

        items = []
        for ob_name in [ob.name for ob in context.scene.objects if ob.type not in ['LIGHT', 'CAMERA']]:
            if ob_name not in objs_in_group:
                if self.do_object_filter and not re.match(pattern, ob_name):
                    continue
                items.append((ob_name, ob_name, ''))
        if not items:
            return return_empty_list(label='No Objects Found')               
        elif self.do_object_filter:
            items.insert(0, ('0', 'Results (%d)' % len(items), '', '', 0))
        else:
            items.insert(0, ('0', 'Select Object', '', '', 0))
        return items  

    def update_do_object_filter(self, context):
        self.selected_obj_name = '0'            

    do_object_filter: BoolProperty(name="Object Filter", 
                                description="Search and add multiple objects",
                                default=False,
                                update=update_do_object_filter)    
    object_search_filter: StringProperty(name="Object Filter Search", default="")       
    selected_obj_name: EnumProperty(name="", items=obj_list_items)       

    def execute(self, context):
        return{'FINISHED'}         

    def draw(self, context):
        layout = self.layout
        scene = context.scene   
        rm = scene.renderman
        layout.separator()
        self._draw_collection(context, layout, rm, "Trace Sets",
                            "renderman.add_remove_object_groups",
                            "scene.renderman",
                            "object_groups", "object_groups_index",
                            default_name='traceSet_%d' % len(rm.object_groups))          

    def draw_objects_item(self, layout, context, item):
        row = layout.row()
        scene = context.scene
        rm = scene.renderman
        group = rm.object_groups[rm.object_groups_index]

        row = layout.row()
        row.separator()   

        row.prop(self, 'do_object_filter', text='', icon='FILTER', icon_only=True)
        if not self.do_object_filter:
            row.prop(self, 'selected_obj_name', text='')
            col = row.column()
            if self.selected_obj_name == '0' or self.selected_obj_name == '':
                col.enabled = False
                op = col.operator("renderman.add_to_group", text='', icon='ADD')
            else:
                col.context_pointer_set('op_ptr', self) 
                col.context_pointer_set('selected_obj', scene.objects[self.selected_obj_name])
                op = col.operator("renderman.add_to_group", text='', icon='ADD')
                op.group_index = rm.object_groups_index    
                op.do_scene_selected = False
        else:
            row.prop(self, 'object_search_filter', text='', icon='VIEWZOOM')
            row = layout.row()  
            row.prop(self, 'selected_obj_name')
            col = row.column()
            if self.selected_obj_name == '0' or self.selected_obj_name == '':
                col.enabled = False
                op = col.operator("renderman.add_to_group", text='', icon='ADD')
            else:
                col.context_pointer_set('op_ptr', self) 
                col.context_pointer_set('selected_obj', scene.objects[self.selected_obj_name])                
                op = col.operator("renderman.add_to_group", text='', icon='ADD')
                op.group_index = rm.object_groups_index
                op.do_scene_selected = False

        row = layout.row()
        
        row.template_list('RENDERMAN_UL_Object_Group_List', "",
                        group, "members", group, 'members_index', rows=6)        

    def draw_item(self, layout, context, item):
        self.draw_objects_item(layout, context, item)

    def invoke(self, context, event):

        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=500)                

classes = [
    RENDER_OT_Renderman_Open_Workspace,
    PRMAN_OT_Renderman_Open_Light_Mixer_Editor,    
    PRMAN_PT_Renderman_Open_Light_Linking,
    PRMAN_OT_Renderman_Open_Groups_Editor,
    RENDERMAN_UL_Object_Group_List,
    RENDERMAN_UL_LightLink_Light_List,
    RENDERMAN_UL_LightLink_Object_List,
    RENDERMAN_UL_LightMixer_Group_Members_List

]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():

    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            rfb_log().debug('Could not unregister class: %s' % str(cls))
            pass                                    