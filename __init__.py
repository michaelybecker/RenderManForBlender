# ##### BEGIN MIT LICENSE BLOCK #####
#
# Copyright (c) 2015 - 2017 Pixar
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
#
# ##### END MIT LICENSE BLOCK #####
import bpy
import bgl
import blf
import time
from . import rman_constants
from .rman_utils import filepath_utils
from .rman_utils import texture_utils
from .rman_utils import prefs_utils
from .rman_utils import string_utils
from .rfb_logger import rfb_log

bl_info = {
    "name": "RenderMan For Blender",
    "author": "Pixar",
    "version": (24, 0, 0),
    "blender": (2, 80, 0),
    "location": "Info Header, render engine menu",
    "description": "RenderMan 24.0 integration",
    "warning": "",
    "category": "Render"}


class PRManRender(bpy.types.RenderEngine):
    bl_idname = 'PRMAN_RENDER'
    bl_label = "RenderMan Render"
    bl_use_preview = True # Turn off preview renders
    bl_use_save_buffers = True
    bl_use_shading_nodes = True # We support shading nodes
    bl_use_shading_nodes_custom = False
    bl_use_eevee_viewport = True # Use Eevee for look dev viewport mode

    def __init__(self):
        from . import rman_render
        self.rman_render = rman_render.RmanRender.get_rman_render()
        if self.rman_render.rman_interactive_running:
            if self.is_preview:
                return
            self.rman_render.stop_render()
        self.rman_render.bl_engine = self

    def __del__(self):
        pass

    def update(self, data, depsgraph):
        pass

    def view_update(self, context, depsgraph):
        '''
        For viewport renders. Blender calls view_update when starting viewport renders
        and/or something changes in the scene.
        '''

        # check if we are already doing a regular render
        if self.rman_render.rman_running:
            return
        
        # if interactive rendering has not started, start it
        if not self.rman_render.rman_interactive_running and self.rman_render.sg_scene is None:
            self.rman_render.start_interactive_render(context, depsgraph)

        if self.rman_render.rman_interactive_running:
            self.rman_render.update_scene(context, depsgraph)   

    def view_draw(self, context, depsgraph):
        '''
        For viewport renders. Blender calls view_draw whenever it redraws the 3D viewport.
        This is where we check for camera moves and draw pxiels from our
        Blender display driver.
        '''
        if self.rman_render.rman_interactive_running:               
            self.rman_render.update_view(context, depsgraph)

        self._draw_pixels(context, depsgraph)


    def render(self, depsgraph):
        '''
        Main render entry point. Blender calls this when doing final renders or preview renders.
        '''
   
        bl_scene = depsgraph.scene_eval

        if self.is_preview:
            prefs = prefs_utils.get_addon_prefs()
            # double check we're not already viewport rendering
            if self.rman_render.rman_interactive_running:
                if prefs.rman_do_preview_renders:
                    rfb_log().error("Cannot preview render while viewport rendering.")
                return            
            if not prefs.rman_do_preview_renders:
                # user has turned off preview renders, just load the placeholder image
                self.rman_render.bl_scene = depsgraph.scene_eval
                self.rman_render._load_placeholder_image()
                return         
            # hopefully, swatch renders are fast enough where this sleep will
            # have minimal impact, but we need to make sure we don't start a new
            # swatch render while one is still rendering
            while self.rman_render.rman_swatch_render_running:
                time.sleep(0.001)
            self.rman_render.start_swatch_render(depsgraph)
          
        elif bl_scene.renderman.enable_external_rendering:
            self.rman_render.start_external_render(depsgraph)               

        else:
            if not self.rman_render.start_render(depsgraph, for_background=bpy.app.background):
                return    

    def _draw_pixels(self, context, depsgraph):     

        scene = depsgraph.scene
        w = context.region.width
        h = context.region.height        

        # Bind shader that converts from scene linear to display space,
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE_MINUS_SRC_ALPHA)
        self.bind_display_space_shader(scene)

        self.rman_render.draw_pixels() 

        self.unbind_display_space_shader()
        bgl.glDisable(bgl.GL_BLEND)

        # Draw text area that RenderMan is running.        
        if prefs_utils.get_addon_prefs().draw_ipr_text:

            pos_x = w / 2 - 100
            pos_y = 20
            blf.enable(0, blf.SHADOW)
            blf.shadow_offset(0, 1, -1)
            blf.shadow(0, 5, 0.0, 0.0, 0.0, 0.8)
            blf.size(0, 32, 36)
            blf.position(0, pos_x, pos_y, 0)
            blf.color(0, 1.0, 0.0, 0.0, 1.0)
            blf.draw(0, "%s" % ('RenderMan Interactive Mode Running'))
            blf.disable(0, blf.SHADOW)           

def set_up_paths():
    import os

    rmantree = filepath_utils.guess_rmantree()
    filepath_utils.set_rmantree(rmantree)
    filepath_utils.set_pythonpath(os.path.join(rmantree, 'bin'))
    it_dir = os.path.dirname(filepath_utils.find_it_path())
    filepath_utils.set_path([os.path.join(rmantree, 'bin'), it_dir])
    pythonbindings = os.path.join(rmantree, 'bin', 'pythonbindings')
    filepath_utils.set_pythonpath(pythonbindings)

def load_addon():
    # if rmantree is ok load the stuff
    from . import preferences

    if filepath_utils.guess_rmantree():
        # else display an error, tell user to correct
        # and don't load anything else
        set_up_paths()
        from . import rman_operators
        from . import rman_ui
        from . import operators
        from . import rman_bl_nodes
        from . import rman_properties
        from . import rman_config
        from . import rman_handlers

        # need this now rather than at beginning to make
        # sure preferences are loaded

        rman_operators.register()
        rman_config.register()
        rman_bl_nodes.register()
        operators.register()
        rman_ui.register()  
        rman_properties.register()      
        #add_handlers(None)
        rman_handlers.register()

    else:
        rfb_log().error(
            "Error loading addon.  Correct RMANTREE setting in addon preferences.")

classes = [
    PRManRender,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    from . import presets
    presets.register()
    from . import preferences
    preferences.register()
    load_addon()

def unregister():
    from . import preferences
    #remove_handlers()
    rman_handlers.unregister()
    rman_bl_nodes.unregister()    
    operators.unregister()
    rman_ui.unregister()
    rman_properties.unregister()
    preferences.unregister()
    from . import presets
    presets.unregister()
    rman_operators.unregister()
    
    for cls in classes:
        bpy.utils.unregister_class(cls)

