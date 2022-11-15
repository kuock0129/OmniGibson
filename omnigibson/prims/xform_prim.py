# Copyright (c) 2021, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.
#
from collections import Iterable, OrderedDict
from typing import Optional, Tuple
from pxr import Gf, Usd, UsdGeom, UsdShade, UsdPhysics
from omni.isaac.core.utils.types import XFormPrimState
from omni.isaac.core.utils.rotations import gf_quat_to_np_array
from omni.isaac.core.utils.prims import (
    get_prim_at_path,
    is_prim_path_valid,
    get_prim_parent,
)
import numpy as np
import carb
from omni.isaac.core.utils.stage import get_current_stage
from omnigibson.prims.prim_base import BasePrim
from omnigibson.prims.material_prim import MaterialPrim
from omnigibson.utils.transform_utils import quat2mat, mat2euler
from omnigibson.utils.usd_utils import BoundingBoxAPI
from scipy.spatial.transform import Rotation as R


class XFormPrim(BasePrim):
    """
    Provides high level functions to deal with an Xform prim and its attributes/ properties.
    If there is an Xform prim present at the path, it will use it. Otherwise, a new XForm prim at
    the specified prim path will be created when self.load(...) is called.

        Note: the prim will have "xformOp:orient", "xformOp:translate" and "xformOp:scale" only post init,
                unless it is a non-root articulation link.

        Args:
            prim_path (str): prim path of the Prim to encapsulate or create.
            name (str): Name for the object. Names need to be unique per scene.
            load_config (None or dict): If specified, should contain keyword-mapped values that are relevant for
                loading this prim at runtime. For this xform prim, the below values can be specified:

                scale (None or float or 3-array): If specified, sets the scale for this object. A single number corresponds
                    to uniform scaling along the x,y,z axes, whereas a 3-array specifies per-axis scaling.
    """

    def __init__(
        self,
        prim_path,
        name,
        load_config=None,
    ):
        # Other values that will be filled in at runtime
        self._default_state = None
        self._binding_api = None
        self._material = None
        self._collision_filter_api = None

        # Run super method
        super().__init__(
            prim_path=prim_path,
            name=name,
            load_config=load_config,
        )

    def _load(self, simulator=None):
        # Define an Xform prim at the current stage, or the simulator's stage if specified
        stage = get_current_stage()
        prim = stage.DefinePrim(self._prim_path, "Xform")

        return prim

    def _post_load(self):
        # run super first
        super()._post_load()

        # Make sure all xforms have pose and scaling info
        self._set_xform_properties()

        # # We need to set the properties if this is not a root link
        # non_root_link_flag = query_parent_path(
        #     prim_path=self._prim_path, predicate=lambda a: get_prim_object_type(a) == "articulation"
        # )
        # if not non_root_link_flag:
        #     self._set_xform_properties()

        # Create collision filter API
        self._collision_filter_api = UsdPhysics.FilteredPairsAPI(self._prim) if \
            self._prim.HasAPI(UsdPhysics.FilteredPairsAPI) else UsdPhysics.FilteredPairsAPI.Apply(self._prim)

        # Create binding API
        self._binding_api = UsdShade.MaterialBindingAPI(self.prim) if \
            self._prim.HasAPI(UsdShade.MaterialBindingAPI) else UsdShade.MaterialBindingAPI.Apply(self.prim)

        # Grab the attached material if it exists
        if self.has_material():
            self._material = MaterialPrim(
                prim_path=self._binding_api.GetDirectBinding().GetMaterialPath().pathString,
                name=f"{self.name}:material",
            )

        # Optionally set the scale and visibility
        if "scale" in self._load_config and self._load_config["scale"] is not None:
            self.scale = self._load_config["scale"]

    def _initialize(self):
        # Always run super first
        super()._initialize()

        # Grab default state
        default_pos, default_ori = self.get_position_orientation()
        self._default_state = XFormPrimState(position=default_pos, orientation=default_ori)

    def _set_xform_properties(self):
        current_position, current_orientation = self.get_position_orientation()
        properties_to_remove = [
            "xformOp:rotateX",
            "xformOp:rotateXZY",
            "xformOp:rotateY",
            "xformOp:rotateYXZ",
            "xformOp:rotateYZX",
            "xformOp:rotateZ",
            "xformOp:rotateZYX",
            "xformOp:rotateZXY",
            "xformOp:rotateXYZ",
            "xformOp:transform",
        ]
        prop_names = self.prim.GetPropertyNames()
        xformable = UsdGeom.Xformable(self.prim)
        xformable.ClearXformOpOrder()
        # TODO: wont be able to delete props for non root links on articulated objects
        for prop_name in prop_names:
            if prop_name in properties_to_remove:
                self.prim.RemoveProperty(prop_name)
        if "xformOp:scale" not in prop_names:
            xform_op_scale = xformable.AddXformOp(UsdGeom.XformOp.TypeScale, UsdGeom.XformOp.PrecisionDouble, "")
            xform_op_scale.Set(Gf.Vec3d([1.0, 1.0, 1.0]))
        else:
            xform_op_scale = UsdGeom.XformOp(self._prim.GetAttribute("xformOp:scale"))

        if "xformOp:translate" not in prop_names:
            xform_op_translate = xformable.AddXformOp(
                UsdGeom.XformOp.TypeTranslate, UsdGeom.XformOp.PrecisionDouble, ""
            )
        else:
            xform_op_translate = UsdGeom.XformOp(self._prim.GetAttribute("xformOp:translate"))

        if "xformOp:orient" not in prop_names:
            xform_op_rot = xformable.AddXformOp(UsdGeom.XformOp.TypeOrient, UsdGeom.XformOp.PrecisionDouble, "")
        else:
            xform_op_rot = UsdGeom.XformOp(self._prim.GetAttribute("xformOp:orient"))
        xformable.SetXformOpOrder([xform_op_translate, xform_op_rot, xform_op_scale])

        self.set_position_orientation(position=current_position, orientation=current_orientation)
        new_position, new_orientation = self.get_position_orientation()
        r1 = R.from_quat(current_orientation).as_matrix()
        r2 = R.from_quat(new_orientation).as_matrix()
        # Make sure setting is done correctly
        assert np.allclose(new_position, current_position, atol=1e-4) and np.allclose(r1, r2, atol=1e-4), \
            f"{self.prim_path}: old_pos: {current_position}, new_pos: {new_position}, " \
            f"old_orn: {current_orientation}, new_orn: {new_orientation}"

    # def reset(self):
    #     """
    #     Resets the prim to its default state (position and orientation).
    #     """
    #     self.set_position_orientation(self._default_state.position, self._default_state.orientation)

    def get_default_state(self):
        """
        Returns:
            XFormPrimState: returns the default state of the prim (position and orientation) that is used after each reset.
        """
        return self._default_state

    def set_default_state(self, position=None, orientation=None):
        """Sets the default state of the prim (position and orientation), that will be used after each reset.

        Args:
            position (Optional[np.ndarray], optional): position in the world frame of the prim. shape is (3, ).
                                                       Defaults to None, which means left unchanged.
            orientation (Optional[np.ndarray], optional): quaternion orientation in the world frame of the prim.
                                                          quaternion is scalar-first (w, x, y, z). shape is (4, ).
                                                          Defaults to None, which means left unchanged.
        """
        if position is not None:
            self._default_state.position = position
        if orientation is not None:
            self._default_state.orientation = orientation
        return

    def update_default_state(self):
        self.set_default_state(*self.get_position_orientation())

    def has_material(self):
        """
        Returns:
            bool: True if there is a visual material bound to this prim. False otherwise
        """
        material_path = self._binding_api.GetDirectBinding().GetMaterialPath().pathString
        return False if material_path == "" else True

    def set_position_orientation(self, position=None, orientation=None):
        """
        Sets prim's pose with respect to the world's frame.

        Args:
            position (Optional[np.ndarray], optional): position in the world frame of the prim. shape is (3, ).
                                                       Defaults to None, which means left unchanged.
            orientation (Optional[np.ndarray], optional): quaternion orientation in the world frame of the prim.
                                                          quaternion is scalar-last (x, y, z, w). shape is (4, ).
                                                          Defaults to None, which means left unchanged.
        """
        current_position, current_orientation = self.get_position_orientation()
        position = current_position if position is None else np.array(position)
        orientation = current_orientation if orientation is None else np.array(orientation)
        orientation = orientation[[3, 0, 1, 2]]     # Flip from x,y,z,w to w,x,y,z

        mat = Gf.Transform()
        mat.SetRotation(Gf.Rotation(Gf.Quatd(*orientation.tolist())))
        mat.SetTranslation(Gf.Vec3d(*position.tolist()))

        # mat.SetScale(Gf.Vec3d(*(self.get_world_scale() / self.scale)))
        # TODO (eric): understand why this (mat.setScale) works - this works empirically but it's unclear why.
        mat.SetScale(Gf.Vec3d(*(self.scale.astype(np.float64))))
        my_world_transform = np.transpose(mat.GetMatrix())

        parent_world_tf = UsdGeom.Xformable(get_prim_parent(self._prim)).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        parent_world_transform = np.transpose(parent_world_tf)

        local_transform = np.matmul(np.linalg.inv(parent_world_transform), my_world_transform)
        transform = Gf.Transform()
        transform.SetMatrix(Gf.Matrix4d(np.transpose(local_transform)))
        calculated_translation = transform.GetTranslation()
        calculated_orientation = transform.GetRotation().GetQuat()
        self.set_local_pose(
            translation=np.array(calculated_translation), orientation=gf_quat_to_np_array(calculated_orientation)[[1, 2, 3, 0]]     # Flip from w,x,y,z to x,y,z,w
        )

    def get_position_orientation(self):
        """
        Gets prim's pose with respect to the world's frame.

        Returns:
            Tuple[np.ndarray, np.ndarray]: first index is position in the world frame of the prim. shape is (3, ).
                                           second index is quaternion orientation in the world frame of the prim.
                                           quaternion is scalar-last (x, y, z, w). shape is (4, ).
        """
        prim_tf = UsdGeom.Xformable(self._prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        transform = Gf.Transform()
        transform.SetMatrix(prim_tf)
        position = transform.GetTranslation()
        orientation = transform.GetRotation().GetQuat()
        return np.array(position), gf_quat_to_np_array(orientation)[[1, 2, 3, 0]]

    def set_position(self, position):
        """
        Set this prim's position with respect to the world frame

        Args:
            position (3-array): (x,y,z) global cartesian position to set
        """
        self.set_position_orientation(position=position)

    def get_position(self):
        """
        Get this prim's position with respect to the world frame

        Returns:
            3-array: (x,y,z) global cartesian position of this prim
        """
        return self.get_position_orientation()[0]

    def set_orientation(self, orientation):
        """
        Set this prim's orientation with respect to the world frame

        Args:
            orientation (4-array): (x,y,z,w) global quaternion orientation to set
        """
        self.set_position_orientation(orientation=orientation)

    def get_orientation(self):
        """
        Get this prim's orientation with respect to the world frame

        Returns:
            4-array: (x,y,z,w) global quaternion orientation of this prim
        """
        return self.get_position_orientation()[1]

    def get_rpy(self):
        """
        Get this prim's orientation with respect to the world frame

        Returns:
            3-array: (roll, pitch, yaw) global euler orientation of this prim
        """
        return mat2euler(quat2mat(self.get_orientation()))

    def get_local_pose(self):
        """Gets prim's pose with respect to the local frame (the prim's parent frame).

        Returns:
            Tuple[np.ndarray, np.ndarray]: first index is position in the local frame of the prim. shape is (3, ).
                                           second index is quaternion orientation in the local frame of the prim.
                                           quaternion is scalar-last (x, y, z, w). shape is (4, ).
        """
        xform_translate_op = self.get_attribute("xformOp:translate")
        xform_orient_op = self.get_attribute("xformOp:orient")
        return np.array(xform_translate_op), gf_quat_to_np_array(xform_orient_op)[[1, 2, 3, 0]]

    def set_local_pose(self, translation=None, orientation=None):
        """Sets prim's pose with respect to the local frame (the prim's parent frame).

        Args:
            translation (Optional[np.ndarray], optional): translation in the local frame of the prim
                                                          (with respect to its parent prim). shape is (3, ).
                                                          Defaults to None, which means left unchanged.
            orientation (Optional[np.ndarray], optional): quaternion orientation in the world frame of the prim.
                                                          quaternion is scalar-last (x, y, z, w). shape is (4, ).
                                                          Defaults to None, which means left unchanged.
        """
        properties = self.prim.GetPropertyNames()
        if translation is not None:
            translation = Gf.Vec3d(*translation.tolist())
            if "xformOp:translate" not in properties:
                carb.log_error(
                    "Translate property needs to be set for {} before setting its position".format(self.name)
                )
            self.set_attribute("xformOp:translate", translation)
        if orientation is not None:
            orientation = np.array(orientation)[[3, 0, 1, 2]]
            if "xformOp:orient" not in properties:
                carb.log_error(
                    "Orient property needs to be set for {} before setting its orientation".format(self.name)
                )
            xform_op = self._prim.GetAttribute("xformOp:orient")
            if xform_op.GetTypeName() == "quatf":
                rotq = Gf.Quatf(*orientation.tolist())
            else:
                rotq = Gf.Quatd(*orientation.tolist())
            xform_op.Set(rotq)
        return

    def get_world_scale(self):
        """Gets prim's scale with respect to the world's frame.

        Returns:
            np.ndarray: scale applied to the prim's dimensions in the world frame. shape is (3, ).
        """
        prim_tf = UsdGeom.Xformable(self._prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        transform = Gf.Transform()
        transform.SetMatrix(prim_tf)
        return np.array(transform.GetScale())

    @property
    def scale(self):
        """Gets prim's scale with respect to the local frame (the parent's frame).

        Returns:
            np.ndarray: scale applied to the prim's dimensions in the local frame. shape is (3, ).
        """
        return np.array(self.get_attribute("xformOp:scale"))

    @scale.setter
    def scale(self, scale):
        """Sets prim's scale with respect to the local frame (the prim's parent frame).

        Args:
            scale (float or np.ndarray): scale to be applied to the prim's dimensions. shape is (3, ).
                                          Defaults to None, which means left unchanged.
        """
        scale = np.array(scale) if isinstance(scale, Iterable) else np.ones(3) * scale
        scale = Gf.Vec3d(*scale.tolist())
        properties = self.prim.GetPropertyNames()
        if "xformOp:scale" not in properties:
            carb.log_error("Scale property needs to be set for {} before setting its scale".format(self.name))
        self.set_attribute("xformOp:scale", scale)

    @property
    def aabb(self):
        """
        Get this xform's actual bounding box, axis-aligned in the world frame

        Returns:
            2-tuple:
                - 3-array: (x,y,z) lower corner of the bounding box
                - 3-array: (x,y,z) upper corner of the bounding box
        """
        return BoundingBoxAPI.compute_aabb(self.prim_path)

    @property
    def aabb_extent(self):
        """
        Get this xform's actual bounding box extent

        Returns:
            3-array: (x,y,z) bounding box
        """
        min_corner, max_corner = self.aabb
        return max_corner - min_corner

    @property
    def aabb_center(self):
        """
        Get this xform's actual bounding box center

        Returns:
            3-array: (x,y,z) bounding box center
        """
        min_corner, max_corner = self.aabb
        return (max_corner + min_corner) / 2.0

    @property
    def material(self):
        """
        Returns:
            None or MaterialPrim: The bound material to this prim, if there is one
        """
        return self._material

    @material.setter
    def material(self, material):
        """
        Set the material @material for this prim. This will also bind the material to this prim

        Args:
            material (MaterialPrim): Material to bind to this prim
        """
        self._binding_api.Bind(material.prim, bindingStrength=UsdShade.Tokens.weakerThanDescendants)
        self._material = material

    def add_filtered_collision_pair(self, prim):
        """
        Adds a collision filter pair with another prim

        Args:
            prim (XFormPrim): Another prim to filter collisions with
        """
        # Add to both this prim's and the other prim's filtered pair
        self._collision_filter_api.GetFilteredPairsRel().AddTarget(prim.prim_path)
        prim._collision_filter_api.GetFilteredPairsRel().AddTarget(self._prim_path)

    def remove_filtered_collision_pair(self, prim):
        """
        Removes a collision filter pair with another prim

        Args:
            prim (XFormPrim): Another prim to remove filter collisions with
        """
        # Add to both this prim's and the other prim's filtered pair
        self._collision_filter_api.GetFilteredPairsRel().RemoveTarget(prim.prim_path)
        prim._collision_filter_api.GetFilteredPairsRel().RemoveTarget(self._prim_path)

    def _dump_state(self):
        pos, ori = self.get_position_orientation()
        return OrderedDict(pos=pos, ori=ori)

    def _load_state(self, state):
        self.set_position_orientation(np.array(state["pos"]), np.array(state["ori"]))

    def _serialize(self, state):
        # We serialize by iterating over the keys and adding them to a list that's concatenated at the end
        # This is a deterministic mapping because we assume the state is an OrderedDict
        return np.concatenate(list(state.values())).astype(float)

    def _deserialize(self, state):
        # We deserialize deterministically by knowing the order of values -- pos, ori
        return OrderedDict(pos=state[0:3], ori=state[3:7]), 7