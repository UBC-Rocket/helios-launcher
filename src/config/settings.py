from pathlib import Path
from enum import Enum
import re

HELIOS_CORE_CONTAINER = "HeliosCore"


def sanitize_image_name(name: str) -> str:
  """Docker image tags can't contain spaces. Lowercase and turn any
  whitespace into underscores (e.g. "Mission Control" -> "mission_control")."""
  return re.sub(r"\s+", "_", name.strip().lower())

ROOT = Path(__file__).parent.parent # src/ directory
TEMP_FOLDER = "tmp"
# Per-config runtime selections (device/port/volume/flag bindings) are cached
# here so they survive a launcher restart.
SETTINGS_FOLDER = "tmp/settings"
ROCKET_CONFIG_FOLDER = "config/rockets"

class Node_Type(Enum):
  NONE = 0
  GITHUB = 1
  LOCAL = 2