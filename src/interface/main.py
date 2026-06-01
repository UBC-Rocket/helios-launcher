"""
User Interface for Project Helios using ImGui.
"""

import os
import re
from imgui_bundle import imgui, immapp, hello_imgui
from utils import TreeNode, TreeUtils, DockerUtils
from .components import TreeComponent, EditorComponent, QuickActions
import serial.tools.list_ports

WINDOW_NAME = "Project Helios Launcher"
DEFAULT_WINDOW_SIZE = (1000, 600)

LEFT_SIDE_WIDTH_RATIO = 0.30 # % of total width for the left sidebar
LEFT_FOOTER_HEIGHT = 300.0 # pixels
LOGO_WIDTH_RATIO = 0.7 # % of available width in the right sidebar for the logo

# Set assets folder for hello_imgui to load images
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(CURRENT_DIR, "assets")
hello_imgui.set_assets_folder(ASSETS_DIR)

# Default flags for the main sections to create a dashboard-like layout
SECTION_FLAGS = (imgui.WindowFlags_.no_scrollbar | 
                 imgui.WindowFlags_.no_move | 
                 imgui.WindowFlags_.no_resize | 
                 imgui.WindowFlags_.no_collapse |
                 imgui.WindowFlags_.no_title_bar)

WHITE_COLOR = (1.0, 1.0, 1.0, 1.0)

class UserInterface:
  """
  ImGui-based UI for displaying a hierarchical tree structure configuration.
  """
  def __init__(self, initial_data: TreeNode):
    self.data = initial_data

    self.next_node_id = 1 # Track the next available node ID for unique identification

    self.tree_utils = TreeUtils()
    self.docker_utils = DockerUtils()

    self.tree_component = TreeComponent(self)
    self.editor_component = EditorComponent()
    self.quick_actions = QuickActions(self)

    runner_params = hello_imgui.RunnerParams()
    runner_params.callbacks.show_gui = self.gui
    runner_params.app_window_params.window_title = WINDOW_NAME
    runner_params.app_window_params.window_geometry.size = DEFAULT_WINDOW_SIZE

    # Load default font and add the font_awesome icons
    runner_params.callbacks.default_icon_font = hello_imgui.DefaultIconFont.font_awesome6

    immapp.run(runner_params=runner_params)

  """
  Renders the main user interface.
  """
  def gui(self):
    # Get the main viewport size for responsive layout
    viewport = imgui.get_main_viewport()
    view_width = viewport.work_size.x
    view_height = viewport.work_size.y
    sidebar_width = view_width * LEFT_SIDE_WIDTH_RATIO

    # Styling for the right sidebar
    imgui.push_style_color(imgui.Col_.window_bg, (0.96, 0.96, 0.97, 1.0)) # Off-white
    imgui.push_style_color(imgui.Col_.text, (0.1, 0.1, 0.1, 1.0)) # Dark text for white bg
    imgui.set_next_window_pos((sidebar_width, 0), imgui.Cond_.always)
    imgui.set_next_window_size((view_width - sidebar_width, view_height), imgui.Cond_.always)
  
    imgui.begin("Right Sidebar", flags=SECTION_FLAGS)
    
    # Render the Helios logo
    avail_x = imgui.get_content_region_avail().x
    logo_w = avail_x * LOGO_WIDTH_RATIO
    imgui.set_cursor_pos_x((avail_x - logo_w) * 0.5)
    hello_imgui.image_from_asset("helios.png", (logo_w, 0))

    imgui.spacing(); imgui.spacing()
    imgui.separator()
    imgui.spacing()

    # Quick Actions grid
    self.quick_actions.render()

    # Dump the image build status
    # TODO: hide this once build finished
    # TODO: dropdown to display full logs?
    for node_id, status in self.docker_utils.build_status.items():
      step = self.docker_utils.build_step.get(node_id, "")
      step_str = f"  [{step}]" if step else ""
      imgui.text(f"{node_id}:  {status}{step_str}")

    # Set launch disabled if the images are not all built
    imgui.set_cursor_pos_y(imgui.get_window_height() - 60)
    launch_disabled = not self.no_container_warnings(self.data)
    if launch_disabled:
      imgui.begin_disabled(True)
    launch = imgui.button("Launch Helios", (avail_x, 40))
    if launch_disabled:
      imgui.end_disabled()

    if launch:
      self.launch_helios()  

    imgui.end()
    imgui.pop_style_color(2)

    # Styling for left sidebar
    imgui.set_next_window_pos((0, 0), imgui.Cond_.always)
    imgui.set_next_window_size((sidebar_width, view_height), imgui.Cond_.always)
    imgui.begin("Hierarchy", flags=SECTION_FLAGS)
    
    # Determine Footer State
    editing_node = self.tree_component.edit_node
    footer_height = LEFT_FOOTER_HEIGHT if editing_node else 0.0 # Only reserve space if editing
    
    imgui.text_disabled("PROJECT OVERVIEW")
    imgui.separator()

    # TODO: Replace with actual stats
    imgui.same_line()
    imgui.text_wrapped("Helios Launcher v1.0\nStatus: Active\nNodes: 12")
    
    imgui.spacing()
    
    imgui.text_disabled("HIERARCHY TREE")
    imgui.separator()
    imgui.spacing()
    self.tree_component.render(-footer_height)

    if editing_node:
      self.editor_component.render(
        node=editing_node, 
        height=footer_height, 
        on_close_callback=self.close_editting_node, 
        on_delete_callback=self.delete_editting_node, 
        available_ports=self.get_ports_list()
      )

    imgui.end()

  def close_editting_node(self):
    self.tree_component.clear_editting_mode()

  def delete_editting_node(self):
    node_to_delete = self.tree_component.edit_node
    if node_to_delete:
      self.tree_component.delete_node(node_to_delete)
      self.tree_component.clear_editting_mode()

  def get_ports_list(self):
    ports = serial.tools.list_ports.comports()
    real_ports = [p for p in ports if p.hwid != "n/a"]
    serial_devices = [f"{p.device}:{p.description}" for p in real_ports]
    udev_symlinks = self._get_udev_serial_symlinks({p.device for p in real_ports})
    return ["None"] + serial_devices + udev_symlinks + ["/dev/snd:All ALSA devices (direwolf/KISS)"]

  def _get_udev_serial_symlinks(self, known_devices: set) -> list[str]:
    dev_dir = "/dev"
    if not os.path.exists(dev_dir):
      return []
    symlinks = []
    try:
      for name in sorted(os.listdir(dev_dir)):
        path = os.path.join(dev_dir, name)
        if not os.path.islink(path):
          continue
        target_basename = os.path.basename(os.readlink(path))
        resolved = os.path.realpath(path)
        # Include if it resolves to a known connected device, or if its target
        # looks like a tty device (catches disconnected udev symlinks by name)
        if resolved in known_devices or re.match(r"tty[A-Z]", target_basename):
          symlinks.append(f"{path}:{name} → {target_basename}")
    except OSError:
      pass
    return symlinks

  def launch_helios(self):
    print("Generating component tree from protobufs and configuration...")
    path = self.tree_utils.generate_component_tree(self.data)
    print(f"Component tree generated at: {path}")

    tree_path = self.tree_utils.get_tree_path()
    self.docker_utils.start_helios(tree_path=tree_path)

  def scan_docker_images(self):
    """ Check if the docker image exists for all nodes starting at the root """
    print("Scanning all nodes for missing docker images...")
    self._scan_node_image_exists(self.data)
    print("Finished docker image scan.")

  def _scan_node_image_exists(self, node: TreeNode) -> None:
    """ If the current node is a leaf, check the image, if not, check its children """
    if node.children == []:
      if not bool(node.image_exists):
        # Only scan if the image hasnt been found yet
        # Works because any changes will automatically change image_exists to None
        node.image_exists, required = self.docker_utils.check_image_exists(node)

        # Load the saved required specs for the image
        node.devices = {d: None for d in required.get('devices', [])}
        node.volumes = required.get('volumes', [])
        node.ports = required.get('ports', {})
    else:
      for child in node.children:
        self._scan_node_image_exists(child)

  def build_missing_docker_images(self):
    """ Build docker images for all nodes missing one """
    print("Building all missing docker images...")
    self._build_docker_image(self.data)
    print("Finished building docker images.")

  def _build_docker_image(self, node: TreeNode) -> None:
    """ 
    If the node has children, build the image for each child
    Build the docker image if image_exists = False 
    Does not build if image_exists = None. Run scan_docker_images() first
    """
    if node.children == []:
      if node.image_exists == False:
        self.docker_utils.build_image(node)
        logs = self.docker_utils.get_logs(node)
        status = self.docker_utils.build_status.get(node.id, "")

        imgui.text(f"Status: {status}")
        for line in logs:
            imgui.text(line)
    else:
      for child in node.children:
        self._build_docker_image(child)
    
  def no_container_warnings(self, node: TreeNode) -> bool:
    if node.children == []:
        return bool(node.image_exists) and not node.warning
    else:
      built = True
      for child in node.children:
        built = self.no_container_warnings(child) and built
      return built
    
  def generate_node_id(self) -> str:
    """ Generates a unique node ID """
    node_id = f"node_{self.next_node_id}"
    self.next_node_id += 1
    return node_id
  
  def get_node_names(self) -> list:
    """ Returns a list of all node names in the tree for dropdowns and validation """
    names = []
    def traverse(node: TreeNode):
      names.append(node.name)
      for child in node.children:
        traverse(child)
    traverse(self.data)
    return names
  
  def add_new_node(self, node: TreeNode, parent_name: str) -> None:
    """ Adds a new node to the tree under the specified parent """
    parent_node = self.find_node_by_name(self.data, parent_name)
    print(f"Adding new node '{node.name}' under parent '{parent_name}'")
    if parent_node is not None:
      parent_node.children.append(node)
    else:
      print(f"Parent node '{parent_name}' not found. Cannot add new node '{node.name}'.")

  def find_node_by_name(self, node: TreeNode, name: str) -> TreeNode | None:
    """ Recursively searches for a node by name and returns it """
    if node.name == name:
      return node
    for child in node.children:
      result = self.find_node_by_name(child, name)
      if result is not None:
        return result
    return None