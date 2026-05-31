from utils import TreeNode
from imgui_bundle import imgui, portable_file_dialogs as pfd
from config import *

class EditorComponent:
  def __init__(self) -> None:
    #self.current_node = None
    pass

  def render(self, node: TreeNode | None, height: float = 0, on_close_callback=None, on_delete_callback=None, available_ports: list = ["None"]) -> None:
    if not node:
      self.current_node = None
      return
    
    # Assume starting with no warning
    node.warning = False

    imgui.set_cursor_pos_y(imgui.get_window_height() - height) # Pin to bottom

    # Use ImGuiWindowFlags_.always_vertical_scrollbar if you expect many settings
    imgui.begin_child("EditPanel", (0, height))
    
    imgui.text_colored((0.3, 0.7, 1.0, 1.0), f"EDITING: {node.name}")
    imgui.spacing()
    imgui.separator()
    imgui.spacing()

    # --- Standard Attributes ---
    changed, new_name = imgui.input_text("Name", node.name, 128)
    if changed:
      self.node_changed(node)
      node.name = new_name

    if node.children == []:    
      changed_type, new_type = imgui.combo("Node Type", node.type.value, [node.name for node in Node_Type])
      if changed_type:
        self.node_changed(node)
        node.type = Node_Type(new_type)

      changed_location, new_location = imgui.input_text("Location", node.location, 128)
      if changed_location:
        self.node_changed(node)
        node.location = new_location

      changed_branch, new_branch = imgui.input_text("Branch", node.branch, 128)
      if changed_branch:
        self.node_changed(node)
        node.branch = new_branch

      changed_skip_spawn, new_skip_spawn = imgui.checkbox("Skip Docker Spawn", node.skip_spawn)
      if changed_skip_spawn:
        self.node_changed(node)
        node.skip_spawn = new_skip_spawn

      imgui.spacing()

      # --- Advanced Settings - Ports ---
      if node.ports:
        self._render_ports(node, available_ports)

      # --- Advanced Settings - Volumes ---
      if node.volumes:
        self._render_volumes(node)
      
    imgui.spacing()
    imgui.separator()
    imgui.spacing()

    # --- Footer ---
    button_width = (imgui.get_content_region_avail()[0] - imgui.get_style().item_spacing.x) / 2

    if imgui.button("Close", (button_width, 0)):
      if on_close_callback:
        on_close_callback()

    imgui.same_line()
    
    if node.id != "root" and node.id != "main":  # Don't allow deleting root or main node
      if imgui.button("Delete", (button_width, 0)):
        if on_delete_callback:
          on_delete_callback()
        
    imgui.end_child()

  def node_changed(self, node: TreeNode):
    """ If any of the basic node information is changed, we need to recheck if the image exists """
    node.image_exists = None

  def _render_ports(self, node: TreeNode, available_ports: list = ["None"]):
    imgui.push_style_color(imgui.Col_.text, (0.6, 0.6, 0.6, 1.0))
    imgui.text("Required Port Bindings (Target : Source)")
    imgui.pop_style_color()
    imgui.spacing()
    for target_key in list(node.ports.keys()):
      source_val = node.ports[target_key]
      imgui.push_id(f"port_{target_key}")

      # Show warning if no port selected
      current_idx = available_ports.index(source_val) if source_val in available_ports else 0
      if current_idx == 0:  # "None" is selected (unbound)
        node.warning = True
        imgui.text_colored((1.0, 0.2, 0.2, 1.0), "⚠")
        imgui.same_line()
      
      imgui.set_next_item_width(100)
      imgui.text(target_key)

      imgui.same_line()
      imgui.text(":")
      imgui.same_line()
      
      imgui.set_next_item_width(imgui.get_content_region_avail().x - 10)
      v_changed, new_idx = imgui.combo("##source", current_idx, available_ports)

      if v_changed:
        node.ports[target_key] = available_ports[new_idx]

      imgui.pop_id()

  def _render_volumes(self, node: TreeNode):
    imgui.push_style_color(imgui.Col_.text, (0.6, 0.6, 0.6, 1.0))
    imgui.text("Required Volume Bindings (Target : Source)")
    imgui.pop_style_color()
    imgui.spacing()
    for i, volume in enumerate(node.volumes):
      source_type = volume['type']
      imgui.push_id(f"port_{i}")          
      
      # Show warning
      if not volume.get('source', ''):
        node.warning = True
        imgui.text_colored((1.0, 0.2, 0.2, 1.0), "⚠")
        imgui.same_line()
      
      imgui.set_next_item_width(100)
      imgui.text(volume['name'])

      imgui.same_line()
      imgui.text(":")
      imgui.same_line()
                
      BROWSE_BTN_WIDTH = 70
      WARNING_WIDTH = 20  # reserve space only if warning is shown

      avail = imgui.get_content_region_avail().x
      current_source = volume.get('source', '')
      path_width = avail - BROWSE_BTN_WIDTH - WARNING_WIDTH
      
      # Truncate path text to fit, using a child region to clip
      imgui.begin_child(f"path_clip_{i}", (path_width, imgui.get_text_line_height()), False)
      display_text = current_source if current_source else "Not selected"
      imgui.push_style_color(imgui.Col_.text, (0.5, 0.5, 0.5, 1.0) if not current_source else (1.0, 1.0, 1.0, 1.0))
      imgui.text(display_text)
      imgui.pop_style_color()
      imgui.end_child()

      # Show full path in tooltip on hover
      if current_source and imgui.is_item_hovered():
        imgui.set_tooltip(current_source)

      imgui.same_line()
      if imgui.button(f"Browse##{i}", (BROWSE_BTN_WIDTH, 0)):
        if source_type == "file":
          dialog = pfd.open_file("Select a file", ".")
          if dialog.result():
            node.volumes[i]['source'] = dialog.result()[0]
        elif source_type == "folder":
          dialog = pfd.select_folder("Select a folder", ".")
          if dialog.result():
            node.volumes[i]['source'] = dialog.result()
        else:
          imgui.text("Invalid volume type")

      imgui.pop_id()