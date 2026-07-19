from pathlib import Path
import generated.helios.config as component
import json

from config.settings import *

TREE_FILE_NAME = "component_tree.json"

class TreeNode:
  def __init__(self, name, node_id, children=None, location: str = "", branch: str = "", hash: str = "", type: Node_Type = Node_Type['NONE'], volumes: dict = {}, devices: dict = {}, ports: dict = {}, flags: list = [], websites: list = [], env: list | None = None):
    self.name: str = name
    self.id: str = node_id
    self.children: list = children or []
    self.location: str = location
    self.branch: str = branch
    self.hash: str = hash
    self.type: Node_Type = type
    self.image_exists: bool | None = None # None, False, True
    self.volumes: dict = volumes
    self.devices: dict = devices
    self.ports: dict = ports
    self.flags: list = flags
    self.websites: list = websites
    # Environment variables as an ordered list of [key, value] pairs. Kept as
    # pairs (not a dict) so rows can be edited live without empty keys colliding.
    self.env: list = env if env is not None else []
    self.warning: bool = False
    self.skip_spawn: bool = False

  def to_dict(self):
    return {
      "name": self.name,
      "id": self.id,
      "location": self.location,
      "branch": self.branch,
      "hash": self.hash,
      "type": self.type.value,
      "image_exists": self.image_exists,
      "volumes": self.volumes,
      "devices": self.devices,
      "ports": self.ports,
      "flags": self.flags,
      "websites": self.websites,
      "env": self.env,
      "children": [child.to_dict() for child in self.children]
    }

class TreeUtils:
  def __init__(self):
    pass

  def generate_component_tree(self, root_node: TreeNode, meta: dict | None = None) -> Path:
    tree_location = self.get_tree_path()

    # Placeholders like $CALLSIGN in a node's flags are replaced with the
    # matching value from the loaded config's mission metadata.
    substitutions = self._build_flag_substitutions(meta)

    def build_proto_node(node: TreeNode) -> component.BaseComponent | None:
      base = component.BaseComponent()
      base.name = node.name

      if not node.children: # Leaf

        # We don't want to pass HeliosCore to Helios, since it shouldn't build itself
        if node.name == HELIOS_CORE_CONTAINER: return None

        leaf = component.Component()

        # Build the nested DockerSpec
        docker_spec = component.DockerSpec()
        docker_spec.image = sanitize_image_name(node.name) or ""
        docker_spec.tag = node.hash or "latest"
        docker_spec.container_name = sanitize_image_name(node.name)

        for vol in node.volumes:  # list of dicts — iterate directly
            v = component.Volume()
            v.source = vol.get("source", "")
            v.target = vol.get("name", "") # TODO: change to "target" once we update the frontend
            v.mode = vol.get("mode", "")
            docker_spec.volumes.append(v)

        for device_target, device_source in node.devices.items():
            d = component.Device()
            d.target = device_target
            d.source = device_source.split(":")[0] if device_source else ""
            docker_spec.devices.append(d)

        for container_port, host_port in node.ports.items():
            p = component.Port()
            p.source = container_port
            p.target = host_port or ""
            docker_spec.ports.append(p)

        # Environment variables (map<string, string>). Values support the same
        # $CALLSIGN-style substitution as flags. Empty keys are dropped.
        docker_spec.env = {
            key: self._substitute_flag(value, substitutions)
            for key, value in node.env
            if key
        }

        leaf.docker_spec = docker_spec

        for flag in node.flags:
            resolved = self._substitute_flag(flag, substitutions)
            leaf.flags.extend(resolved.split())
        leaf.websites.extend(node.websites)

        base.leaf = leaf
      else: # Branch
        branch = component.ComponentGroup()
        for child in node.children:
          # Recursively build child BaseComponents
          proto_child = build_proto_node(child)
          if not proto_child == None:
            branch.children.append(proto_child)
        base.branch = branch
      
      return base

    root_proto_node = build_proto_node(root_node)

    component_tree = component.ComponentTree()
    component_tree.root = root_proto_node
    component_tree.version = "1.0.0"

    with open(tree_location, "w") as f:
      json_string = component_tree.to_json(
        indent=2, 
        include_default_values=True, 
      )
      f.write(json_string)

    return tree_location

  def save_tree_as_dict(self, root: TreeNode, file_name: str = "configuration.json"):
    file_path = ROOT / ROCKET_CONFIG_FOLDER / file_name

    # New format: the tree lives under "nodes" alongside other mission config.
    # Preserve any existing top-level config in the file and only replace the tree.
    data = {}
    if file_path.exists():
      with open(file_path, "r") as f:
        try:
          existing = json.load(f)
          if isinstance(existing, dict) and "nodes" in existing:
            data = existing
        except json.JSONDecodeError:
          data = {}

    data["nodes"] = root.to_dict()

    with open(file_path, "w") as f:
      json.dump(data, f, indent=2)

  def load_tree_from_dict(self, file_name: str = "configuration.json") -> TreeNode:
    node, _ = self.load_config(file_name)
    return node

  def load_config(self, file_name: str = "configuration.json") -> tuple[TreeNode, dict]:
    """Loads a config file, returning both the component tree and any top-level
    mission metadata (everything except the "nodes" tree)."""
    file_path = Path(ROOT) / ROCKET_CONFIG_FOLDER / file_name

    if not file_path.exists():
      raise FileNotFoundError(f"No tree configuration found at {file_path}")

    with open(file_path, "r") as f:
      data = json.load(f)

    # New format stores the component tree under "nodes" alongside mission
    # config. Old format (e.g. IREC2026-CloudBurst.json) stored it at the root.
    if isinstance(data, dict) and "nodes" in data:
      meta = {k: v for k, v in data.items() if k != "nodes"}
      tree_data = data["nodes"]
    else:
      meta = {}
      tree_data = data

    return self._dict_to_node(tree_data), meta

  def _dict_to_node(self, data: dict) -> TreeNode:
    """Recursively converts a dictionary back into a TreeNode object."""
    children_data = data.pop("children", [])

    # Backwards compat: old configs stored device mappings under "ports"
    if "devices" in data:
      devices = data.pop("devices", {})
      ports = data.pop("ports", {})
    else:
      devices = data.pop("ports", {})
      ports = {}

    if not isinstance(ports, dict):
      ports = {}
    if not isinstance(devices, dict):
      devices = {}

    # env is stored as a list of [key, value] pairs. Accept a dict too, for
    # forward/backward compatibility with hand-edited configs.
    env = data.pop("env", [])
    if isinstance(env, dict):
      env = [[k, v] for k, v in env.items()]
    if isinstance(env, list):
      env = [[str(p[0]), str(p[1])] for p in env
             if isinstance(p, (list, tuple)) and len(p) == 2]
    else:
      env = []

    node = TreeNode(
      name=data.get("name"),
      node_id=data.get("id"),
      location=data.get("location", ""),
      branch=data.get("branch", ""),
      hash=data.get("hash", ""),
      type=Node_Type(data.get("type", 0)),
      volumes=data.pop("volumes", {}),
      devices=devices,
      ports=ports,
      flags=data.get("flags", []),
      websites=data.get("websites", []),
      env=env
    )

    node.image_exists = None

    for child_dict in children_data:
      node.children.append(self._dict_to_node(child_dict))

    return node
  
  def get_tree_path(self) -> Path:
    return Path(ROOT) / TEMP_FOLDER / TREE_FILE_NAME

  # --- Flag placeholder substitution ---------------------------------------
  # Node flags may contain placeholders like $CALLSIGN that get filled in from
  # the loaded config's mission metadata when the component tree is generated.

  def _build_flag_substitutions(self, meta: dict | None) -> dict:
    """Maps $UPPER_KEY -> str(value) for every scalar metadata field
    (e.g. {"callsign": "VE7XYZ"} -> {"$CALLSIGN": "VE7XYZ"})."""
    subs = {}
    if not meta:
      return subs
    for key, value in meta.items():
      if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        continue
      subs[f"${key.upper()}"] = str(value)
    return subs

  def _substitute_flag(self, flag: str, subs: dict) -> str:
    for placeholder, value in subs.items():
      flag = flag.replace(placeholder, value)
    return flag

  def update_config_meta(self, config_name: str, field: str, value) -> None:
    """Updates a single top-level metadata field (e.g. callsign) in the config
    file on disk, preserving the rest of the file."""
    file_path = Path(ROOT) / ROCKET_CONFIG_FOLDER / f"{config_name}.json"
    if not file_path.exists():
      return
    with open(file_path, "r") as f:
      try:
        data = json.load(f)
      except json.JSONDecodeError:
        return
    if not isinstance(data, dict):
      return
    data[field] = value
    with open(file_path, "w") as f:
      json.dump(data, f, indent=2)

  # --- Per-config runtime settings cache -----------------------------------
  # These persist the user's device/port/volume/flag selections for a given
  # config so they don't have to be re-entered on every launcher restart.

  def _settings_path(self, config_name: str) -> Path:
    return Path(ROOT) / SETTINGS_FOLDER / f"{config_name}.json"

  def has_config_settings(self, config_name: str) -> bool:
    return self._settings_path(config_name).exists()

  def save_config_settings(self, config_name: str, root: TreeNode) -> None:
    """Snapshots the runtime selections (devices/ports/volumes/flags) for every
    node, keyed by node id, into a tmp file tied to this config."""
    snapshot: dict = {}

    def collect(node: TreeNode):
      snapshot[node.id] = {
        "devices": node.devices,
        "ports": node.ports,
        "volumes": node.volumes,
        "flags": node.flags,
        "env": node.env,
      }
      for child in node.children:
        collect(child)

    collect(root)

    path = self._settings_path(config_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
      json.dump({"config": config_name, "nodes": snapshot}, f, indent=2)

  def apply_config_settings(self, config_name: str, root: TreeNode) -> bool:
    """Restores previously saved selections onto matching nodes (by id).
    Returns True if a settings file was found and applied."""
    path = self._settings_path(config_name)
    if not path.exists():
      return False

    with open(path, "r") as f:
      try:
        saved = json.load(f).get("nodes", {})
      except json.JSONDecodeError:
        return False

    def restore(node: TreeNode):
      s = saved.get(node.id)
      if s:
        node.devices = s.get("devices", node.devices)
        node.ports = s.get("ports", node.ports)
        node.volumes = s.get("volumes", node.volumes)
        node.flags = s.get("flags", node.flags)
        node.env = s.get("env", node.env)
        node.image_exists = None  # force a re-scan after restoring bindings
      for child in node.children:
        restore(child)

    restore(root)
    return True