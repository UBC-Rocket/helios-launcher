from platform import node

from imgui_bundle import imgui
from config.settings import *
from utils.tree import TreeNode

class QuickActions:
  def __init__(self, interface):
    self.interface = interface # User interface class
    self.add_node_modal = False
    self.open_save_modal = False
    self.open_load_modal = False
    self.file_name = ""
    self.load_configs = []
    self.load_selected_index = 0
    self.new_node = None
    self.new_parent = None
    self.new_parent_index = 0

  def _refresh_load_configs(self):
    """Scans for .json configs and strips extensions for display."""
    import os
    try:
      self.load_configs = sorted([
        os.path.splitext(f)[0]
        for f in os.listdir(ROOT / ROCKET_CONFIG_FOLDER)
        if f.endswith(".json")
      ])
    except OSError:
      self.load_configs = []
    self.load_selected_index = 0

  def render(self):
    imgui.text_disabled("QUICK ACTIONS")
    if imgui.begin_table("Actions", 2):
      imgui.table_next_row()
      imgui.table_next_column()
      if imgui.button("Add Component", (-1, 40)): 
        self.add_node_modal = True
      imgui.table_next_column()
      if imgui.button("Global Settings", (-1, 40)): pass
      imgui.table_next_row()
      imgui.table_next_column()
      if imgui.button("Scan Existing Docker Images", (-1, 40)):
        self.interface.scan_docker_images()
      imgui.table_next_column()
      if imgui.button("Build Missing Docker Images", (-1, 40)):
        self.interface.build_missing_docker_images()
      imgui.table_next_row()
      imgui.table_next_column()
      if imgui.button("Save Configuration", (-1, 40)): 
        print("Opening configuration modal...")
        self.open_save_modal = True
        self.file_name = ""
      imgui.table_next_column()
      if imgui.button("Load Configuration", (-1, 40)): 
        print("Opening load modal...")
        self._refresh_load_configs()  # scan fresh every time modal opens
        self.open_load_modal = True
      imgui.end_table()

    if self.open_save_modal:
      imgui.open_popup("save_config_modal")
      self.open_save_modal = False
    if self.open_load_modal:
      imgui.open_popup("load_config_modal")
      self.open_load_modal = False
    if self.add_node_modal:
      imgui.open_popup("add_node_modal")
      self.add_node_modal = False

    self._render_save_modal()
    self._render_load_modal()
    self._render_add_modal()

  def _render_save_modal(self):
    # Window styling
    self._render_popup_styling()

    imgui.set_next_window_size((380, 0))  # fixed width, auto height

    opened, show = imgui.begin_popup_modal("save_config_modal", True,
                                           imgui.WindowFlags_.no_title_bar |
                                           imgui.WindowFlags_.no_resize)
    imgui.pop_style_var(5)
    imgui.pop_style_color(6)

    if not opened:
      return

    # Title row
    imgui.push_style_color(imgui.Col_.text, (0.88, 0.90, 0.94, 1.00))
    imgui.text("Save Configuration")
    imgui.pop_style_color()

    imgui.push_style_color(imgui.Col_.separator, (0.25, 0.27, 0.32, 1.00))
    imgui.separator()
    imgui.pop_style_color()

    imgui.spacing()

    # Filename input
    imgui.push_style_color(imgui.Col_.text_disabled, (0.45, 0.48, 0.55, 1.00))
    imgui.text_disabled("Filename")
    imgui.pop_style_color()

    imgui.set_next_item_width(-1)
    imgui.push_style_color(imgui.Col_.text, (0.88, 0.90, 0.94, 1.00))
    changed, self.file_name = imgui.input_text(
      "##filename", self.file_name, 256,
      #imgui.InputTextFlags_.auto_select_all
    )
    imgui.pop_style_color()

    imgui.push_style_color(imgui.Col_.text_disabled, (0.40, 0.42, 0.50, 1.00))
    imgui.text_disabled(f'  Will save as:  "{self.file_name or "..."}.json"')
    imgui.pop_style_color()

    imgui.spacing()
    imgui.spacing()

    # Buttons
    button_width = (imgui.get_content_region_avail()[0] - 10) / 2

    # Save — accented blue
    imgui.push_style_color(imgui.Col_.button,         (0.20, 0.45, 0.90, 1.00))
    imgui.push_style_color(imgui.Col_.button_hovered, (0.28, 0.53, 1.00, 1.00))
    imgui.push_style_color(imgui.Col_.button_active,  (0.15, 0.38, 0.80, 1.00))
    can_save = bool(self.file_name.strip())
    if not can_save:
      imgui.begin_disabled()
    if imgui.button("Save", (button_width, 36)):
      self.interface.tree_utils.save_tree_as_dict(
        self.interface.data, self.file_name.strip() + ".json"
      )
      imgui.close_current_popup()
      self.open_save_modal = False
    if not can_save:
      imgui.end_disabled()
    imgui.pop_style_color(3)

    imgui.same_line()

    # Cancel — subtle ghost button
    imgui.push_style_color(imgui.Col_.button,         (0.20, 0.21, 0.25, 1.00))
    imgui.push_style_color(imgui.Col_.button_hovered, (0.26, 0.27, 0.32, 1.00))
    imgui.push_style_color(imgui.Col_.button_active,  (0.16, 0.17, 0.20, 1.00))
    if imgui.button("Cancel", (button_width, 36)):
      imgui.close_current_popup()
      self.open_save_modal = False
    imgui.pop_style_color(3)

    imgui.end_popup()

  def _render_load_modal(self):
    # Refresh config list when modal opens
    if not hasattr(self, 'load_configs'):
      self.load_configs = []
    if not hasattr(self, 'load_selected_index'):
      self.load_selected_index = 0

    # Window styling
    self._render_popup_styling()

    imgui.set_next_window_size((380, 0))

    opened, show = imgui.begin_popup_modal("load_config_modal", True,
                                           imgui.WindowFlags_.no_title_bar |
                                           imgui.WindowFlags_.no_resize)
    imgui.pop_style_var(5)
    imgui.pop_style_color(6)

    if not opened:
      return

    # Title
    imgui.push_style_color(imgui.Col_.text, (0.88, 0.90, 0.94, 1.00))
    imgui.text("Load Configuration")
    imgui.pop_style_color()

    imgui.push_style_color(imgui.Col_.separator, (0.25, 0.27, 0.32, 1.00))
    imgui.separator()
    imgui.pop_style_color()

    imgui.spacing()

    # Combo box
    imgui.push_style_color(imgui.Col_.text_disabled, (0.45, 0.48, 0.55, 1.00))
    imgui.text_disabled("Saved Configurations")
    imgui.pop_style_color()

    if self.load_configs:
      imgui.set_next_item_width(-1)
      imgui.push_style_color(imgui.Col_.text, (0.88, 0.90, 0.94, 1.00))
      # Combo items are display names (no path, no extension)
      preview = self.load_configs[self.load_selected_index]
      if imgui.begin_combo("##load_combo", preview):
        for i, name in enumerate(self.load_configs):
          is_selected = (i == self.load_selected_index)
          _, clicked = imgui.selectable(name, is_selected)
          if clicked:
            self.load_selected_index = i
          if is_selected:
            imgui.set_item_default_focus()
        imgui.end_combo()
      imgui.pop_style_color()

      imgui.push_style_color(imgui.Col_.text_disabled, (0.40, 0.42, 0.50, 1.00))
      imgui.text_disabled(f'  Will load:  "{self.load_configs[self.load_selected_index]}.json"')
      imgui.pop_style_color()
    else:
      # Empty state
      imgui.push_style_color(imgui.Col_.frame_bg, (0.08, 0.09, 0.11, 1.00))
      imgui.push_style_color(imgui.Col_.text,     (0.40, 0.42, 0.50, 1.00))
      imgui.set_next_item_width(-1)
      imgui.begin_combo("##load_combo_empty", "No saved configurations found")
      imgui.end_combo()
      imgui.pop_style_color(2)

    imgui.spacing()
    imgui.spacing()

    # Buttons
    button_width = (imgui.get_content_region_avail()[0] - 10) / 2

    # Load — accented blue
    imgui.push_style_color(imgui.Col_.button,         (0.20, 0.45, 0.90, 1.00))
    imgui.push_style_color(imgui.Col_.button_hovered, (0.28, 0.53, 1.00, 1.00))
    imgui.push_style_color(imgui.Col_.button_active,  (0.15, 0.38, 0.80, 1.00))
    can_load = bool(self.load_configs)
    if not can_load:
      imgui.begin_disabled()
    if imgui.button("Load", (button_width, 36)):
      filename = self.load_configs[self.load_selected_index] + ".json"
      self.interface.data = self.interface.tree_utils.load_tree_from_dict(filename)
      imgui.close_current_popup()
      self.open_load_modal = False
    if not can_load:
      imgui.end_disabled()
    imgui.pop_style_color(3)

    imgui.same_line()

    # Cancel
    imgui.push_style_color(imgui.Col_.button,         (0.20, 0.21, 0.25, 1.00))
    imgui.push_style_color(imgui.Col_.button_hovered, (0.26, 0.27, 0.32, 1.00))
    imgui.push_style_color(imgui.Col_.button_active,  (0.16, 0.17, 0.20, 1.00))
    if imgui.button("Cancel", (button_width, 36)):
      imgui.close_current_popup()
      self.open_load_modal = False
    imgui.pop_style_color(3)

    imgui.end_popup()

  def _render_add_modal(self):
    # Window styling
    self._render_popup_styling()

    imgui.set_next_window_size((380, 0))  # fixed width, auto height

    opened, show = imgui.begin_popup_modal("add_node_modal", True,
                                           imgui.WindowFlags_.no_title_bar |
                                           imgui.WindowFlags_.no_resize)
    imgui.pop_style_var(5)
    imgui.pop_style_color(6)

    if not opened:
      return

    if self.new_node is not None:
      node = self.new_node
    else:
      node = TreeNode(
        name="New Component",
        node_id=self.interface.generate_node_id()
      )
      self.new_node = node

    # Title row
    imgui.push_style_color(imgui.Col_.text, (0.88, 0.90, 0.94, 1.00))
    imgui.text("Add Node")
    imgui.pop_style_color()

    imgui.push_style_color(imgui.Col_.separator, (0.25, 0.27, 0.32, 1.00))
    imgui.separator()
    imgui.pop_style_color()

    imgui.spacing()
    imgui.push_style_color(imgui.Col_.text, (0.88, 0.90, 0.94, 1.00))
    
    nodes = self.interface.get_node_names()
    changed_parent, new_parent = imgui.combo("Parent", self.new_parent_index, ["None"] + nodes)
    if changed_parent:
      self.new_parent_index = new_parent
      # Index 0 is "None", so subtract 1 to get actual node index
      self.new_parent = nodes[new_parent - 1] if new_parent > 0 else None

    imgui.spacing()
    imgui.separator()
    imgui.spacing()

    changed, new_name = imgui.input_text("Name", node.name, 128)
    if changed:
      node.name = new_name

    if node.children == []:    
      changed_type, new_type = imgui.combo("Node Type", node.type.value, [node.name for node in Node_Type])
      if changed_type:
        node.type = Node_Type(new_type)

      changed_location, new_location = imgui.input_text("Location", node.location, 128)
      if changed_location:
        node.location = new_location

      changed_branch, new_branch = imgui.input_text("Branch", node.branch, 128)
      if changed_branch:
        node.branch = new_branch

      changed_skip_spawn, new_skip_spawn = imgui.checkbox("Skip Docker Spawn", node.skip_spawn)
      if changed_skip_spawn:
        node.skip_spawn = new_skip_spawn

      imgui.spacing()
    imgui.pop_style_color()

    # Buttons
    button_width = (imgui.get_content_region_avail()[0] - 10) / 2

    # Save — accented blue
    imgui.push_style_color(imgui.Col_.button,         (0.20, 0.45, 0.90, 1.00))
    imgui.push_style_color(imgui.Col_.button_hovered, (0.28, 0.53, 1.00, 1.00))
    imgui.push_style_color(imgui.Col_.button_active,  (0.15, 0.38, 0.80, 1.00))

    if not self.new_parent:
      disabled = True    
      imgui.begin_disabled()
    else:
      disabled = False
    if imgui.button("Save", (button_width, 36)):
      self.interface.add_new_node(self.new_node, self.new_parent)
      imgui.close_current_popup()
      self.add_node_modal = False
      self.new_node = None
      self.new_parent = None
      self.new_parent_index = 0
    if disabled:
      imgui.end_disabled()
    imgui.pop_style_color(3)

    imgui.same_line()

    # Cancel — subtle ghost button
    imgui.push_style_color(imgui.Col_.button,         (0.20, 0.21, 0.25, 1.00))
    imgui.push_style_color(imgui.Col_.button_hovered, (0.26, 0.27, 0.32, 1.00))
    imgui.push_style_color(imgui.Col_.button_active,  (0.16, 0.17, 0.20, 1.00))
    if imgui.button("Cancel", (button_width, 36)):
      imgui.close_current_popup()
      self.add_node_modal = False
      self.new_node = None
      self.new_parent = None
      self.new_parent_index = 0
    imgui.pop_style_color(3)

    imgui.end_popup()

  def _render_popup_styling(self):
    imgui.push_style_var(imgui.StyleVar_.window_padding,  (24, 20))
    imgui.push_style_var(imgui.StyleVar_.window_rounding, 10.0)
    imgui.push_style_var(imgui.StyleVar_.frame_padding,   (10, 7))
    imgui.push_style_var(imgui.StyleVar_.frame_rounding,  6.0)
    imgui.push_style_var(imgui.StyleVar_.item_spacing,    (10, 10))

    imgui.push_style_color(imgui.Col_.popup_bg,         (0.13, 0.14, 0.17, 1.00))
    imgui.push_style_color(imgui.Col_.border,           (0.25, 0.27, 0.32, 1.00))
    imgui.push_style_color(imgui.Col_.frame_bg,         (0.08, 0.09, 0.11, 1.00))
    imgui.push_style_color(imgui.Col_.frame_bg_hovered, (0.12, 0.13, 0.16, 1.00))
    imgui.push_style_color(imgui.Col_.text,             (0.88, 0.90, 0.94, 1.00))
    imgui.push_style_color(imgui.Col_.text_disabled,    (0.45, 0.48, 0.55, 1.00))

    imgui.set_next_window_size((380, 0))