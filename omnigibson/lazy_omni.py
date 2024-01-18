import sys
from omnigibson.utils.lazy_import_utils import LazyImporter

_import_structure = {
    "carb": ["carb"],
    "omni": ["omni", "physics", "ui", "usd", "timeline"],
    "omni.graph": ["core"],
    "omni.isaac.core.articulations": ["ArticulationView"],
    "omni.isaac.core.materials": ["PhysicsMaterial"],
    "omni.isaac.core.objects.ground_plane": ["GroundPlane"],
    "omni.isaac.core.prims": ["RigidPrimView"],
    "omni.isaac.core.simulation_context": ["SimulationContext"],
    "omni.isaac.core.utils.bounds": [
        "recompute_extents", "compute_aabb", "create_bbox_cache", "compute_combined_aabb"
    ],
    "omni.isaac.core.utils.extensions": ["enable_extension"],
    "omni.isaac.core.utils.prims": [
        "delete_prim", "define_prim", "get_prim_at_path", "get_prim_children", 
        "get_prim_object_type", "get_prim_parent", "get_prim_path", 
        "get_prim_property", "get_prim_type_name", "is_prim_ancestral", 
        "is_prim_no_delete", "is_prim_path_valid", "move_prim", 
        "query_parent_path", "set_prim_property"
    ],
    "omni.isaac.core.utils.rotations": ["gf_quat_to_np_array"],
    "omni.isaac.core.utils.semantics": ["add_update_semantics"],
    "omni.isaac.core.utils.stage": [
        "add_reference_to_stage", "get_current_stage", "get_stage_units", 
        "traverse_stage", "open_stage", "create_new_stage"
    ],
    "omni.isaac.core.utils.transformations": ["tf_matrix_from_pose"],
    "omni.isaac.dynamic_control": ["_dynamic_control"],
    "omni.isaac.kit": ["SimulationApp"],
    "omni.isaac.range_sensor": ["_range_sensor"],
    "omni.isaac.sensor": ["_sensor"],
    "omni.isaac.synthetic_utils.visualization": ["colorize_bboxes"],
    "omni.isaac.version": ["get_version"],
    "omni.kit.commands": ["execute"],
    "omni.kit.primitive.mesh": ["command"],
    "omni.kit.primitive.mesh.command": ["CreateMeshPrimWithDefaultXformCommand"],
    "omni.kit.primitive.mesh.evaluators.cone": ["ConeEvaluator"],
    "omni.kit.primitive.mesh.evaluators.cube": ["CubeEvaluator"],
    "omni.kit.primitive.mesh.evaluators.cylinder": ["CylinderEvaluator"],
    "omni.kit.primitive.mesh.evaluators.disk": ["DiskEvaluator"],
    "omni.kit.primitive.mesh.evaluators.plane": ["PlaneEvaluator"],
    "omni.kit.primitive.mesh.evaluators.sphere": ["SphereEvaluator"],
    "omni.kit.primitive.mesh.evaluators.torus": ["TorusEvaluator"],
    "omni.kit.viewport.utility": ["create_viewport_window"],
    "omni.kit.viewport.window": ["get_viewport_window_instances"],
    "omni.kit.widget.settings": ["SettingType"],
    "omni.kit.widget.stage.context_menu": ["ContextMenu"],
    "omni.kit.xr.core": ["XRDeviceClass", "XRCore", "XRCoreEventType"],
    "omni.kit.xr.ui.stage.common": ["XRAvatarManager"],
    "omni.log": ["get_log", "SettingBehavior"],
    "omni.particle.system.core.scripts.core": ["Core"],
    "omni.particle.system.core.scripts.utils": ["Utils"],
    "omni.physx": [
        "get_physx_interface", "get_physx_simulation_interface", "get_physx_scene_query_interface"
    ],
    "omni.physx.bindings._physx": [
        "SimulationEvent", "ContactEventType", "SETTING_UPDATE_TO_USD", 
        "SETTING_UPDATE_VELOCITIES_TO_USD", "SETTING_NUM_THREADS", "SETTING_UPDATE_PARTICLES_TO_USD"
    ],
    "omni.physx.scripts": ["physicsUtils", "particleUtils"],
    "omni.rtx.window.settings": ["RendererSettingsFactory"],
    "omni.syntheticdata": ["sensors", "helpers", "_syntheticdata"],
    "omni.usd": ["get_shader_from_material"],
    "omni.usd.commands": ["CopyPrimCommand", "CreatePrimCommand"],
    "pxr": [
        "Gf", "PhysicsSchemaTools", "PhysxSchema", "Sdf", "Usd", 
        "UsdGeom", "UsdLux", "UsdPhysics", "UsdShade", "UsdUtils", "Vt"
    ],
    "pxr.Sdf": ["ValueTypeNames"],
}

sys.modules[__name__] = LazyImporter(__name__, globals()["__file__"], _import_structure)
