import functools
import importlib
import importlib.util
import pathlib
from typing import Optional

import yaml

from .dataclass import SystemKey, TextToMusicSystemMetadata
from .path import SYSTEMS_DIR, SYSTEMS_PRIVATE_DIR
from .system import TextToMusicSystem


@functools.lru_cache
def _parse_registry(
    registry_dir: pathlib.Path,
) -> dict[SystemKey, TextToMusicSystemMetadata]:
    result = {}
    yaml_path = registry_dir / "registry.yaml"
    with open(yaml_path, "r") as f:
        for system_tag, system_kwargs in yaml.safe_load(f).items():
            variants = system_kwargs.pop("variants", {})
            if len(variants) == 0:
                raise TypeError(f"System {system_tag} must have at least one variant")
            for variant_tag, variant_kwargs in variants.items():
                system_key = SystemKey(system_tag=system_tag, variant_tag=variant_tag)
                combined_kwargs = system_kwargs.copy()
                descriptions = [
                    d
                    for d in [
                        system_kwargs.get("description", ""),
                        variant_kwargs.get("description", ""),
                    ]
                    if len(d) > 0
                ]
                combined_kwargs.update(variant_kwargs)
                combined_kwargs["description"] = " ".join(descriptions)
                if registry_dir == SYSTEMS_PRIVATE_DIR and not combined_kwargs.get(
                    "private", False
                ):
                    raise ValueError(f"Private system {system_key} marked as public.")
                try:
                    system_metadata = TextToMusicSystemMetadata(
                        key=system_key,
                        registry_dir=registry_dir,
                        **combined_kwargs,
                    )
                except TypeError as e:
                    raise TypeError(
                        f"Error parsing variant {variant_tag} for system {system_tag}: {e}"
                    ) from e
                result[system_key] = system_metadata
    return result


def get_registered_systems(
    registry_dirs: Optional[list[pathlib.Path]] = None,
) -> dict[SystemKey, TextToMusicSystemMetadata]:
    if registry_dirs is None:
        registry_dirs = [SYSTEMS_DIR, SYSTEMS_PRIVATE_DIR]
        registry_dirs = [d for d in registry_dirs if d.is_dir()]
    result = {}
    for registry_dir in registry_dirs:
        entry = _parse_registry(registry_dir)
        if any(k in result for k in entry):
            raise ValueError(f"Duplicate system key in {registry_dir}")
        result.update(entry)
    return result


@functools.lru_cache
def get_system_metadata(system_key: SystemKey) -> TextToMusicSystemMetadata:
    if system_key not in get_registered_systems():
        raise ValueError(f"System {system_key} not found")
    return get_registered_systems()[system_key]


def init_system(system_key: SystemKey, lazy: bool = True) -> TextToMusicSystem:
    variant_metadata = get_system_metadata(system_key)

    # Load module
    module_path = variant_metadata.registry_dir / f"{variant_metadata.module_name}.py"
    spec = importlib.util.spec_from_file_location(
        variant_metadata.module_name, module_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cls = getattr(module, variant_metadata.class_name)
    instance = cls(**variant_metadata.init_kwargs)
    if not lazy:
        instance.prepare()
    return instance
