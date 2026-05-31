import os
from utils import TreeNode
from interface import UserInterface
from config.settings import *

# Mock data
root_data = TreeNode("Helios", "root", [
    TreeNode(HELIOS_CORE_CONTAINER, "main", location="https://github.com/helios-data/helios-core", type=Node_Type.GITHUB, branch="main"),
    TreeNode("FALCON", "1", [
        TreeNode("Telemetry", "2", location="https://github.com/UBC-Rocket/helios-cots-telemetry", type=Node_Type.GITHUB, branch="main"),
    ]),
    TreeNode("Services", "6", [
      TreeNode("Dashboard", "7", location="https://github.com/helios-data/helios-dashboard", type=Node_Type.GITHUB, branch="main"),
      TreeNode("Livestreaming", "8", location="https://github.com/helios-data/helios-livestreaming", type=Node_Type.GITHUB, branch="main"),
    ]),
])

# Prune leftover stopped containers from build step
os.environ["DOCKER_BUILDKIT"] = "1"

os.makedirs(ROOT / TEMP_FOLDER, exist_ok=True)

if __name__ == "__main__":
  UserInterface(root_data)