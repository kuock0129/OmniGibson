import numpy as np

from pxr import Usd, UsdGeom, Sdf, Gf, Vt, PhysxSchema
import omni
from omni.isaac.core.utils.prims import get_prim_at_path
from omni.isaac.core.utils.stage import get_current_stage
from omni.physx.scripts import physicsUtils, particleUtils
from omnigibson.utils.usd_utils import array_to_vtarray


def create_physx_particle_system(
    prim_path,
    physics_scene_path,
    particle_contact_offset,
    visual_only=False,
    smoothing=True,
    anisotropy=True,
    isosurface=True,
):
    """
    Creates an Omniverse physx particle system at @prim_path. For post-processing visualization effects (anisotropy,
    smoothing, isosurface), see the Omniverse documentation
    (https://docs.omniverse.nvidia.com/app_create/prod_extensions/ext_physics.html?highlight=isosurface#post-processing-for-fluid-rendering)
    for more info

    Args:
        prim_path (str): Stage path to where particle system should be created
        physics_scene_path (str): Stage path to where active physicsScene prim is defined
        particle_contact_offset (float): Distance between particles which triggers a collision (m)
        visual_only (bool): If True, will disable collisions between particles and non-particles,
            as well as self-collisions
        smoothing (bool): Whether to smooth particle positions or not
        anisotropy (bool): Whether to apply anisotropy post-processing when visualizing particles. Stretches generated
            particles in order to make the particle cluster surface appear smoother. Useful for fluids
        isosurface (bool): Whether to apply isosurface mesh to visualize particles. Uses a monolithic surface that
            can have materials attached to it, useful for visualizing fluids

    Returns:
        UsdGeom.PhysxParticleSystem: Generated particle system prim
    """
    # TODO: Add sanity check to make sure GPU dynamics are enabled
    # Create particle system
    stage = get_current_stage()
    particle_system = PhysxSchema.PhysxParticleSystem.Define(stage, prim_path)
    particle_system.CreateSimulationOwnerRel().SetTargets([physics_scene_path])

    # Use a smaller particle size for nicer fluid, and let the sim figure out the other offsets
    particle_system.CreateParticleContactOffsetAttr().Set(particle_contact_offset)

    # Possibly disable collisions if we're only visual
    if visual_only:
        particle_system.GetGlobalSelfCollisionEnabledAttr().Set(False)
        particle_system.GetNonParticleCollisionEnabledAttr().Set(False)

    if anisotropy:
        # apply api and use all defaults
        PhysxSchema.PhysxParticleAnisotropyAPI.Apply(particle_system.GetPrim())

    if smoothing:
        # apply api and use all defaults
        PhysxSchema.PhysxParticleSmoothingAPI.Apply(particle_system.GetPrim())

    if isosurface:
        # apply api and use all defaults
        PhysxSchema.PhysxParticleIsosurfaceAPI.Apply(particle_system.GetPrim())
        # Make sure we're not casting shadows
        primVarsApi = UsdGeom.PrimvarsAPI(particle_system.GetPrim())
        primVarsApi.CreatePrimvar("doNotCastShadows", Sdf.ValueTypeNames.Bool).Set(True)
        # tweak anisotropy min, max, and scale to work better with isosurface:
        if anisotropy:
            ani_api = PhysxSchema.PhysxParticleAnisotropyAPI.Apply(particle_system.GetPrim())
            ani_api.CreateScaleAttr().Set(5.0)
            ani_api.CreateMinAttr().Set(1.0)  # avoids gaps in surface
            ani_api.CreateMaxAttr().Set(2.0)

    return particle_system


def bind_material(prim_path, material_path):
    """
    Binds material located at @material_path to the prim located at @prim_path.

    Args:
        prim_path (str): Stage path to prim to bind material to
        material_path (str): Stage path to material to be bound
    """
    omni.kit.commands.execute(
        "BindMaterialCommand",
        prim_path=prim_path,
        material_path=material_path,
        strength=None,
    )


def get_prototype_path_from_particle_system_path(particle_system_path):
    """
    Grabs the particle prototype directory prim path from the particle system path. This is different from before
    because Omni no longer allows for meshes to be nested within each other.

    Args:
        particle_system_path (str): Prim path to the particle system of interest

    Returns:
        str: Corresponding directory to the particle system's prototypes
    """
    return f"{particle_system_path}Prototypes"


def create_physx_particleset_pointinstancer(
    name,
    particle_system_path,
    particle_group,
    positions,
    self_collision=True,
    fluid=False,
    particle_mass=None,
    particle_density=None,
    orientations=None,
    velocities=None,
    angular_velocities=None,
    scales=None,
    prototype_prim_paths=None,
    prototype_indices=None,
    enabled=True,
) -> Usd.Prim:
    """
    Creates a particle set instancer based on a UsdGeom.PointInstancer at @prim_path on the current stage, with
    the specified parameters.

    Args:
        name (str): Name for this point instancer
        particle_system_path (str): Stage path to particle system that simulates the set
        particle_group (int): ID for this particle set. Particles from different groups will automatically collide
            with each other. Particles in the same group will have collision behavior dictated by @self_collision
        positions (list of 3-tuple or np.array): Particle (x,y,z) positions either as a list or a (N, 3) numpy array
        self_collision (bool): Whether to enable particle-particle collision within the set
            (as defined by @particle_group) or not
        fluid (bool): Whether to simulated the particle set as fluid or not
        particle_mass (None or float): If specified, should be per-particle mass. Otherwise, will be
            inferred from @density. Note: Either @particle_mass or @particle_density must be specified!
        particle_density (None or float): If specified, should be per-particle density and is used to compute total
            point set mass. Otherwise, will be inferred from @density. Note: Either @particle_mass or
            @particle_density must be specified!
        orientations (None or list of 4-array or np.array): Particle (x,y,z,w) quaternion orientations, either as a
            list or a (N, 4) numpy array. If not specified, all will be set to canonical orientation (0, 0, 0, 1)
        velocities (None or list of 3-array or np.array): Particle (x,y,z) velocities either as a list or a (N, 3)
            numpy array. If not specified, all will be set to 0
        angular_velocities (None or list of 3-array or np.array): Particle (x,y,z) angular velocities either as a
            list or a (N, 3) numpy array. If not specified, all will be set to 0
        scales (None or list of 3-array or np.array): Particle (x,y,z) scales either as a list or a (N, 3)
            numpy array. If not specified, all will be set to 1.0
        prototype_prim_paths (None or str or list of str): Stage path(s) to the prototypes to reference for this
            particle set. If None, will generate a default sphere called "particlePrototype" as the prototype.
        prototype_indices (None or list of int): If specified, should specify which prototype should be used for
            each particle. If None, will use all 0s (i.e.: the first prototype created)
        enabled (bool): Whether to enable this particle instancer. If not enabled, then no physics will be used

    Returns:
        UsdGeom.PointInstancer: Created point instancer prim
    """
    stage = get_current_stage()
    n_particles = len(positions)
    particle_system = get_prim_at_path(particle_system_path)

    # Make sure no prototype doesn't already exist at this point
    prim_path = f"{particle_system_path}/{name}"
    assert not stage.GetPrimAtPath(prim_path), f"Cannot create PointInstancer prim, prim already exists at {prim_path}!"

    # Create point instancer
    assert not stage.GetPrimAtPath(prim_path)
    instancer = UsdGeom.PointInstancer.Define(stage, prim_path)

    # Create particle instance prototypes if none are specified
    prototype_root_path = f"{get_prototype_path_from_particle_system_path(particle_system_path=particle_system_path)}/{name}"
    stage.DefinePrim(prototype_root_path, "Scope")
    if prototype_prim_paths is None:
        prototype_path = f"{prototype_root_path}/particlePrototype"
        UsdGeom.Sphere.Define(stage, prototype_path)
        prototype_prim_paths = [prototype_path]
    else:
        # We copy the prototypes at the prims
        # We need to make copies currently because omni behavior is weird (frozen particles)
        # if multiple instancers share the same prototype prim for some reason
        new_prototype_prim_paths = []
        for i, p_path in enumerate(prototype_prim_paths):
            new_path = f"{prototype_root_path}/particlePrototype{i}"
            omni.kit.commands.execute("CopyPrim", path_from=p_path, path_to=new_path)
            new_prototype_prim_paths.append(new_path)
        prototype_prim_paths = new_prototype_prim_paths

    # Add prototype mesh prim paths to the prototypes relationship attribute for this point set
    # We also hide the prototype if we're using an isosurface
    mesh_list = instancer.GetPrototypesRel()
    is_isosurface = particle_system.HasAPI(PhysxSchema.PhysxParticleIsosurfaceAPI) and \
                    particle_system.GetAttribute("physxParticleIsosurface:isosurfaceEnabled").Get()

    for prototype_prim_path in prototype_prim_paths:
        # Make sure this prim is visible first
        if is_isosurface:
            UsdGeom.Imageable(get_prim_at_path(prototype_prim_path)).MakeInvisible()
        else:
            UsdGeom.Imageable(get_prim_at_path(prototype_prim_path)).MakeVisible()
        # Add target
        mesh_list.AddTarget(Sdf.Path(prototype_prim_path))

    # Set particle instance default data
    prototype_indices = [0] * n_particles if prototype_indices is None else prototype_indices
    if orientations is None:
        orientations = np.zeros((n_particles, 4))
        orientations[:, -1] = 1.0
    orientations = np.array(orientations)[:, [3, 0, 1, 2]]  # x,y,z,w --> w,x,y,z
    velocities = np.zeros((n_particles, 3)) if velocities is None else velocities
    angular_velocities = np.zeros((n_particles, 3)) if angular_velocities is None else angular_velocities
    scales = np.ones((n_particles, 3)) if scales is None else scales
    assert particle_mass is not None or particle_density is not None, \
        "Either particle mass or particle density must be specified when creating particle instancer!"
    particle_mass = 0.0 if particle_mass is None else particle_mass
    particle_density = 0.0 if particle_density is None else particle_density

    # Set particle states
    instancer.GetProtoIndicesAttr().Set(prototype_indices)
    instancer.GetPositionsAttr().Set(array_to_vtarray(arr=positions, element_type=Gf.Vec3f))
    instancer.GetOrientationsAttr().Set(array_to_vtarray(arr=orientations, element_type=Gf.Quath))
    instancer.GetVelocitiesAttr().Set(array_to_vtarray(arr=velocities, element_type=Gf.Vec3f))
    instancer.GetAngularVelocitiesAttr().Set(array_to_vtarray(arr=angular_velocities, element_type=Gf.Vec3f))
    instancer.GetScalesAttr().Set(array_to_vtarray(arr=scales, element_type=Gf.Vec3f))

    instancer_prim = instancer.GetPrim()

    particleUtils.configure_particle_set(
        instancer_prim,
        particle_system_path,
        self_collision,
        fluid,
        particle_group,
        particle_mass * n_particles,
        particle_density,
    )

    # Set whether the instancer is enabled or not
    instancer_prim.GetAttribute("physxParticle:particleEnabled").Set(enabled)

    # Add ability to translate instancer as well
    physicsUtils.set_or_add_translate_op(instancer, Gf.Vec3f(0, 0, 0))

    return instancer_prim