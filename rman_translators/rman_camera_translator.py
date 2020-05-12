from .rman_translator import RmanTranslator
from ..rman_sg_nodes.rman_sg_camera import RmanSgCamera
from ..rman_sg_nodes.rman_sg_node import RmanSgNode
from ..rman_utils import transform_utils
from ..rman_utils import property_utils
from ..rman_utils import object_utils
from ..rman_utils import scene_utils
from mathutils import Matrix, Vector
import math

def _render_get_resolution_(r):
    xres = int(r.resolution_x * r.resolution_percentage * 0.01)
    yres = int(r.resolution_y * r.resolution_percentage * 0.01)
    return xres, yres    

def _render_get_aspect_(r, camera=None, x=-1, y=-1):
    if x != -1 and y != -1:
        xratio = x * r.pixel_aspect_x / 200.0
        yratio = y * r.pixel_aspect_y / 200.0        
    else:
        xres, yres = _render_get_resolution_(r)
        xratio = xres * r.pixel_aspect_x / 200.0
        yratio = yres * r.pixel_aspect_y / 200.0

    if camera is None or camera.type != 'PERSP':
        fit = 'AUTO'
    else:
        fit = camera.sensor_fit

    if fit == 'HORIZONTAL' or fit == 'AUTO' and xratio > yratio:
        aspectratio = xratio / yratio
        xaspect = aspectratio
        yaspect = 1.0
    elif fit == 'VERTICAL' or fit == 'AUTO' and yratio > xratio:
        aspectratio = yratio / xratio
        xaspect = 1.0
        yaspect = aspectratio
    else:
        aspectratio = xaspect = yaspect = 1.0

    return xaspect, yaspect, aspectratio    

class RmanCameraTranslator(RmanTranslator):

    def __init__(self, rman_scene):
        super().__init__(rman_scene)
        self.bl_type = 'CAMERA'
        self.s_rightHanded = self.rman_scene.rman.Types.RtMatrix4x4(1.0,0.0,0.0,0.0,
                                                               0.0,1.0,0.0,0.0,
                                                               0.0,0.0,-1.0,0.0,
                                                               0.0,0.0,0.0,1.0) 

    def _set_orientation(self, rman_sg_camera):
        camtransform = self.rman_scene.rman.Types.RtMatrix4x4()
        camtransform.Identity()
        rman_sg_camera.sg_node.SetOrientTransform(self.s_rightHanded)        

    def update_transform_num_samples(self, rman_sg_camera, motion_steps ):
        rman_sg_camera.sg_node.SetTransformNumSamples(len(motion_steps))

    def _update_viewport_transform(self, rman_sg_camera):
        mtx = self.rman_scene.context.region_data.view_matrix.inverted()
        v = transform_utils.convert_matrix(mtx)
        if rman_sg_camera.cam_matrix == v:
            return 
        rman_sg_camera.cam_matrix = v
        rman_sg_camera.sg_node.SetTransform( v )    

    def _update_render_cam_transform(self, ob, rman_sg_camera, index=0):

        cam = ob.data
        mtx = ob.matrix_world

        v = transform_utils.convert_matrix(mtx)
        if rman_sg_camera.cam_matrix == v:
            return

        rman_sg_camera.cam_matrix = v
        if rman_sg_camera.is_transforming:
            rman_sg_camera.sg_node.SetTransformSample(index, v, rman_sg_camera.motion_steps[index] )              
        else:
            rman_sg_camera.sg_node.SetTransform( v )                            

    def update_transform(self, ob, rman_sg_camera, index=0):
        if self.rman_scene.is_viewport_render:
            self._update_viewport_transform(rman_sg_camera)
        else:
            self._update_render_cam_transform(ob, rman_sg_camera, index)

    def _export_viewport_cam(self, db_name=""):  
        sg_camera = self.rman_scene.sg_scene.CreateCamera(db_name)
        rman_sg_camera = RmanSgCamera(self.rman_scene, sg_camera, db_name)
        self._update_viewport_cam(rman_sg_camera)
        self._set_orientation(rman_sg_camera)
        self._update_viewport_transform(rman_sg_camera)  
        return rman_sg_camera        

    def _export_render_cam(self, ob, db_name=""):
        sg_camera = self.rman_scene.sg_scene.CreateCamera(db_name)
        rman_sg_camera = RmanSgCamera(self.rman_scene, sg_camera, db_name)
        if self.rman_scene.do_motion_blur:
            rman_sg_camera.is_transforming = object_utils.is_transforming(ob)
            mb_segs = self.rman_scene.bl_scene.renderman.motion_segments
            if ob.renderman.motion_segments_override:
                mb_segs = ob.renderman.motion_segments
            if mb_segs > 1:
                subframes = scene_utils._get_subframes_(mb_segs, self.rman_scene.bl_scene)
                rman_sg_camera.motion_steps = subframes  
                self.update_transform_num_samples(rman_sg_camera, subframes )                
            else:
                rman_sg_camera.is_transforming = False
        self._update_render_cam(ob, rman_sg_camera)
        self._set_orientation(rman_sg_camera)
        self._update_render_cam_transform(ob, rman_sg_camera)
        return rman_sg_camera                  

    def export(self, ob, db_name=""):
        if self.rman_scene.is_viewport_render:
            return self._export_viewport_cam(db_name)
        else:
            return self._export_render_cam(ob, db_name)

    def update(self, ob, rman_sg_camera):
        if self.rman_scene.is_viewport_render:
            return self._update_viewport_cam(rman_sg_camera)
        else:
            return self._update_render_cam(ob, db_name)        

    def _update_viewport_cam(self, rman_sg_camera):
        region = self.rman_scene.context.region
        region_data = self.rman_scene.context.region_data
        width = region.width
        height = region.height
        proj = None
        fov = -1

        options = self.rman_scene.sg_scene.GetOptions()
        prop = rman_sg_camera.sg_node.GetProperties()

        if region_data.view_perspective == 'CAMERA':
            rman_sg_camera.is_perspective = True
            ob = self.rman_scene.bl_scene.camera
            if self.rman_scene.context.space_data.use_local_camera:
                ob = self.rman_scene.context.space_data.camera
            cam = ob.data
            
            r = self.rman_scene.bl_scene.render

            xaspect, yaspect, aspectratio = _render_get_aspect_(r, cam, x=width, y=height)

            # magic zoom formula copied from blenderseed, which got it from cycles
            zoom = 4 / ((math.sqrt(2) + self.rman_scene.context.region_data.view_camera_zoom / 50) ** 2)           

            lens = cam.lens
            sensor = cam.sensor_height \
                if cam.sensor_fit == 'VERTICAL' else cam.sensor_width
                     
            fov = 360.0 * math.atan((sensor * 0.5) / lens / aspectratio) / math.pi

            if rman_sg_camera.rman_fov != -1:
                rman_sg_camera.rman_fov = fov                

            proj = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrCamera", "proj")
            projparams = proj.params         
            projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_fov, fov) 

            # shift and offset            
            offset = tuple(self.rman_scene.context.region_data.view_camera_offset)
            dx = 2.0 * (aspectratio * cam.shift_x + offset[0] * xaspect * 2.0)
            dy = 2.0 * (aspectratio * cam.shift_y + offset[1] * yaspect * 2.0)       
            
            xaspect *= zoom
            yaspect *= zoom 
            prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, (-xaspect+dx, xaspect+dx, -yaspect+dy, yaspect+dy), 4)        

        elif region_data.view_perspective ==  'PERSP': 
            rman_sg_camera.is_perspective = True
            ob = self.rman_scene.context.space_data.camera
            cam = ob.data
            
            r = self.rman_scene.bl_scene.render

            xaspect, yaspect, aspectratio = _render_get_aspect_(r, cam, x=width, y=height)

            # 2.25 zoom value copied from blenderseed
            #zoom = 2.25        
            zoom = 4 / ((math.sqrt(2) + self.rman_scene.context.region_data.view_camera_zoom / 50) ** 2)           

            lens = self.rman_scene.context.space_data.lens
            sensor = cam.sensor_height \
                if cam.sensor_fit == 'VERTICAL' else cam.sensor_width
                     
            fov = 360.0 * math.atan((sensor * 0.5) / lens / aspectratio) / math.pi

            if rman_sg_camera.rman_fov != -1:
                rman_sg_camera.rman_fov = fov                

            proj = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrCamera", "proj")
            projparams = proj.params         
            projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_fov, fov)   

            xaspect *= zoom
            yaspect *= zoom
            prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, (-xaspect, xaspect, -yaspect, yaspect), 4)           

        else:
            # orthographic
            rman_sg_camera.is_perspective = True
            ob = self.rman_scene.context.space_data.camera
            cam = ob.data
            
            r = self.rman_scene.bl_scene.render

            xaspect, yaspect, aspectratio = _render_get_aspect_(r, cam, x=width, y=height)

            # 2.25 zoom value copied from blenderseed
            zoom = 2.25        
            lens = self.rman_scene.context.space_data.lens
            sensor = cam.sensor_height \
                if cam.sensor_fit == 'VERTICAL' else cam.sensor_width

            ortho_scale = region_data.view_distance * sensor / lens
            xaspect = xaspect * ortho_scale / (aspectratio * 2.0)
            yaspect = yaspect * ortho_scale / (aspectratio * 2.0)
            proj = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrOrthographic", "proj")

            xaspect *= zoom
            yaspect *= zoom            
            prop.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, (-xaspect, xaspect, -yaspect, yaspect), 4)    

        if (width == rman_sg_camera.res_width) and (height == rman_sg_camera.res_height):
            return            

        if (rman_sg_camera.res_width != width):
            rman_sg_camera.cam_matrix = -1

        rman_sg_camera.res_width = width
        rman_sg_camera.res_height = height    

        options.SetFloat(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatPixelAspectRatio, 1.0)   
        options.SetIntegerArray(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatResolution, (width, height), 2)

        self.rman_scene.sg_scene.SetOptions(options)
        rman_sg_camera.sg_node.SetProjection(proj)
        rman_sg_camera.sg_node.SetProperties(prop)            
        rman_sg_camera.sg_node.SetRenderable(True)         

    def _update_render_cam(self, ob, rman_sg_camera):

        r = self.rman_scene.bl_scene.render
        cam = ob.data
        rm = self.rman_scene.bl_scene.renderman
        cam_rm = cam.renderman

        xaspect, yaspect, aspectratio = _render_get_aspect_(r, cam)

        options = self.rman_scene.sg_scene.GetOptions()

        if self.rman_scene.bl_scene.render.use_border and not self.rman_scene.bl_scene.render.use_crop_to_border:
            min_x = self.rman_scene.bl_scene.render.border_min_x
            max_x = self.rman_scene.bl_scene.render.border_max_x
            if (min_x >= max_x):
                min_x = 0.0
                max_x = 1.0
            min_y = 1.0 - self.rman_scene.bl_scene.render.border_min_y
            max_y = 1.0 - self.rman_scene.bl_scene.render.border_max_y
            if (min_y >= max_y):
                min_y = 0.0
                max_y = 1.0

            options.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_CropWindow, (min_x, max_x, min_y, max_y), 4)

        proj = None

        dx = 0
        dy = 0
        if cam_rm.projection_type != 'none':
            # use pxr Camera
            if cam_rm.get_projection_name() == 'PxrCamera':
                lens = cam.lens
                sensor = cam.sensor_height \
                    if cam.sensor_fit == 'VERTICAL' else cam.sensor_width
                fov = 360.0 * \
                    math.atan((sensor * 0.5) / lens / aspectratio) / math.pi
                proj = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrCamera", "proj")
                projparams = proj.params
                projparams.SetFloat("fov", fov )     
            else:
                proj = self.rman_scene.rman.SGManager.RixSGShader("Projection", cam_rm.get_projection_node(), "proj")
            rman_sg_node = RmanSgNode(self.rman_scene, proj, "")                           
            property_utils.property_group_to_rixparams(cam_rm.get_projection_node(), rman_sg_node, proj)
        elif cam.type == 'PERSP':

            lens = cam.lens

            sensor = cam.sensor_height \
                if cam.sensor_fit == 'VERTICAL' else cam.sensor_width

            fov = 360.0 * math.atan((sensor * 0.5) / lens / aspectratio) / math.pi
         
            proj = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrCamera", "proj")

            projparams = proj.params
            
            dx = 2.0 * (aspectratio * cam.shift_x) 
            dy = 2.0 * (aspectratio * cam.shift_y)   

            projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_fov, fov)

            if cam_rm.rman_use_dof:
                if cam_rm.rman_focus_object:
                    dof_focal_distance = (ob.location - cam_rm.rman_focus_object.location).length
                else:
                    dof_focal_distance = cam_rm.rman_focus_distance
                if dof_focal_distance > 0.0:
                    dof_focal_length = (cam.lens * 0.001)
                    projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_fStop, cam_rm.rman_aperture_fstop)
                    projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_focalLength, dof_focal_length)
                    projparams.SetFloat(self.rman_scene.rman.Tokens.Rix.k_focalDistance, dof_focal_distance)
                
                     
        elif cam.type == 'PANO':
            proj = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrSphereCamera", "proj")
            projparams = proj.params
            projparams.SetFloat("hsweep", 360)
            projparams.SetFloat("vsweep", 180)           
        else:
            lens = cam.ortho_scale
            xaspect = xaspect * lens / (aspectratio * 2.0)
            yaspect = yaspect * lens / (aspectratio * 2.0)
            proj = self.rman_scene.rman.SGManager.RixSGShader("Projection", "PxrOrthographic", "proj")

        # convert the crop border to screen window, flip y
        resolution = _render_get_resolution_(self.rman_scene.bl_scene.render)
        if self.rman_scene.bl_scene.render.use_border and self.rman_scene.bl_scene.render.use_crop_to_border:
            screen_min_x = -xaspect + 2.0 * self.rman_scene.bl_scene.render.border_min_x * xaspect
            screen_max_x = -xaspect + 2.0 * self.rman_scene.bl_scene.render.border_max_x * xaspect
            screen_min_y = -yaspect + 2.0 * (self.rman_scene.bl_scene.render.border_min_y) * yaspect
            screen_max_y = -yaspect + 2.0 * (self.rman_scene.bl_scene.render.border_max_y) * yaspect

            options.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, (screen_min_x, screen_max_x, screen_min_y, screen_max_y), 4)

            res_x = resolution[0] * (self.rman_scene.bl_scene.render.border_max_x -
                                    self.rman_scene.bl_scene.render.border_min_x)
            res_y = resolution[1] * (self.rman_scene.bl_scene.render.border_max_y -
                                    self.rman_scene.bl_scene.render.border_min_y)

            options.SetIntegerArray(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatResolution, (int(res_x), int(res_y)), 2)
            options.SetFloat(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatPixelAspectRatio, 1.0)        
        else:            
            if cam.type == 'PANO':
                options.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, (-1, 1, -1, 1), 4)
            else:
                options.SetFloatArray(self.rman_scene.rman.Tokens.Rix.k_Ri_ScreenWindow, (-xaspect+dx, xaspect+dx, -yaspect+dy, yaspect+dy), 4)
            options.SetIntegerArray(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatResolution, (resolution[0], resolution[1]), 2)
            options.SetFloat(self.rman_scene.rman.Tokens.Rix.k_Ri_FormatPixelAspectRatio, 1.0)

        self.rman_scene.sg_scene.SetOptions(options)

        rman_sg_camera.sg_node.SetProjection(proj)

        prop = rman_sg_camera.sg_node.GetProperties()

        # clipping planes         
        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_nearClip, cam.clip_start)
        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_farClip, cam.clip_end)

        # aperture
        prop.SetInteger(self.rman_scene.rman.Tokens.Rix.k_apertureNSides, cam_rm.rman_aperture_blades)
        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_apertureAngle, cam_rm.rman_aperture_rotation)
        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_apertureRoundness, cam_rm.rman_aperture_roundness)
        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_apertureDensity, cam_rm.rman_aperture_density)

        prop.SetFloat(self.rman_scene.rman.Tokens.Rix.k_dofaspect, cam_rm.rman_aperture_ratio)    

        rman_sg_camera.sg_node.SetProperties(prop)
    