from pathlib import Path
import generated.helios.config as component
import json

from config.settings import *

TREE_FILE_NAME = "component_tree.json"

class TreeNode:
  def __init__(self, name, node_id, children=None, location: str = "", branch: str = "", hash: str = "", type: Node_Type = Node_Type['NONE'], volumes: dict = {}, devices: dict = {}, ports: dict = {}, flags: list = [], websites: list = []):
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
      "children": [child.to_dict() for child in self.children]
    }

class TreeUtils:
  def __init__(self):
    pass

  def generate_component_tree(self, root_node: TreeNode) -> Path:
    tree_location = self.get_tree_path()

    def build_proto_node(node: TreeNode) -> component.BaseComponent | None:
      base = component.BaseComponent()
      base.name = node.name

      if not node.children: # Leaf

        # We don't want to pass HeliosCore to Helios, since it shouldn't build itself
        if node.name == HELIOS_CORE_CONTAINER: return None

        leaf = component.Component()

        # Build the nested DockerSpec
        docker_spec = component.DockerSpec()
        docker_spec.image = node.name.lower() or ""
        docker_spec.tag = node.hash or "latest"
        docker_spec.container_name = node.name    

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

        leaf.docker_spec = docker_spec

        for flag in node.flags:
            leaf.flags.extend(flag.split())
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
    with open(ROOT / ROCKET_CONFIG_FOLDER / file_name, "w") as f:
      data = root.to_dict()
      json.dump(data, f, indent=2)
    
    pass

  def load_tree_from_dict(self, file_name: str = "configuration.json") -> TreeNode:
    file_path = Path(ROOT) / ROCKET_CONFIG_FOLDER / file_name
        
    if not file_path.exists():
      raise FileNotFoundError(f"No tree configuration found at {file_path}")

    with open(file_path, "r") as f:
      data = json.load(f)
    
    return self._dict_to_node(data)

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
      websites=data.get("websites", [])
    )

    node.image_exists = None

    for child_dict in children_data:
      node.children.append(self._dict_to_node(child_dict))

    return node
  
  def get_tree_path(self) -> Path:
    return Path(ROOT) / TEMP_FOLDER / TREE_FILE_NAME