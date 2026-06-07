import docker
from docker.errors import DockerException
from docker.models.containers import Container
import threading
from .github import GithubUtils
from .tree import TreeNode
from config import *
from git.exc import GitCommandError
import platform
import re
import json
import time
import sys

REMOVE_BUILD_INTERMEDIATES = True 

DOCKER_VOLUME_CONFIG = {
  '/var/run/docker.sock': {
    'bind': '/var/run/docker.sock',
    'mode': 'rw' # Read-write access
  }
}

class DockerUtils:

  def __init__(self):
    self.client = self._get_docker_client()
    self.github_utils = GithubUtils()

    self.build_logs: dict[str, list[str]] = {}   # node.id → list of log lines
    self.build_status: dict[str, str] = {}        # node.id → "building" | "done" | "error"
    self.build_step: dict[str, str] = {}  # ← node.id → "5/15"

    # TODO: UPDATE THIS DYNAMICALLY
    self.runtime_hash = f"123456789-{time.time()}"

  def check_image_exists(self, node: TreeNode) -> tuple[bool, dict]:
    node_hash = node.hash

    if not node.hash or node.hash == "latest":
      branch = node.branch or 'HEAD'
      try:
        node_hash = self.github_utils.get_latest_hash(node.location, branch) if node.type == Node_Type['GITHUB'] else None
      except (GitCommandError, Exception) as e:
        print(f"[WARNING] Could not fetch latest hash for {node.name} (no internet or remote unreachable: {e}). Falling back to any locally built image on branch '{branch}'.")
        node_hash = None

    filters = {
      "label": [
        f"location={node.location}",
        f"type={node.type.value}",
        f"hash={node_hash}"
      ]
    }

    images = self.client.images.list(name=node.name.lower(), filters=filters)

    if not images and node_hash is None:
      # Fallback already active — no hash filter
      filters_no_hash = {
        "label": [
          f"location={node.location}",
          f"type={node.type.value}",
        ]
      }
      images = self.client.images.list(name=node.name.lower(), filters=filters_no_hash)
    elif not images and node_hash is not None:
      # Hash was resolved but no matching image — try without hash as fallback
      branch = node.branch or 'HEAD'
      print(f"[WARNING] No image found for {node.name} at hash {node_hash[:8]}. Falling back to any locally built image on branch '{branch}'.")
      filters_no_hash = {
        "label": [
          f"location={node.location}",
          f"type={node.type.value}",
        ]
      }
      images = self.client.images.list(name=node.name.lower(), filters=filters_no_hash)

    if not images:
      return False, {"devices": [], "volumes": [], "ports": {}}

    found_labels = images[0].labels

    devices_raw = found_labels.get("devices", "[]")
    volumes_raw = found_labels.get("volumes", "[]")
    ports_raw = found_labels.get("ports", "{}")

    devices = json.loads(devices_raw)
    volumes = json.loads(volumes_raw)
    ports = json.loads(ports_raw)
    if not isinstance(ports, dict):
      ports = {}

    if devices or volumes:
      node.warning = True

    return True, {
      "devices": devices,
      "volumes": volumes,
      "ports": ports,
    }

  def build_image(self, node: TreeNode) -> None:
    """ Starts a background thread to build the image, streaming logs into self.build_logs """
    self.build_logs[node.name] = []
    self.build_status[node.name] = "building"
    thread = threading.Thread(target=self._build_worker, args=(node,), daemon=True)
    thread.start()

  def _build_worker(self, node: TreeNode) -> None:
    try:
      if node.type == Node_Type['GITHUB']:
        path = ROOT / TEMP_FOLDER / node.name
        hash = self.github_utils.clone_repo(
            target_dir=path,
            repo_url=node.location,
            branch=node.branch or None,
            hash=node.hash or None
        )
      else:
        path = Path(node.location)
        hash = None

      self.build_logs[node.name].append(f"Building docker image for {node.name}...\n")

      # Get the required configuration ports/volumes/devices
      with open(path / 'config.json', 'r') as file:
        data = json.load(file)

        ports_raw = data.get('ports', [])
        # Backwards compat: old config had ports as list of device path strings
        if ports_raw and isinstance(ports_raw[0], str):
          node.devices = {d: None for d in ports_raw}
          node.ports = {}
        else:
          node.devices = {d: None for d in data.get('devices', [])}
          node.ports = {p['source']: p.get('target', p['source']) for p in ports_raw}

        node.volumes = data.get('volumes', [])
        node.websites = data.get('websites', [])
        node.flags = data.get('flags', [])

        if node.devices or node.volumes:
          node.warning = True

      # Build the docker image
      build_stream = self.client.api.build(
        path=str(path),
        tag=node.name.lower(),
        labels={
          "type": str(node.type.value),
          "location": node.location,
          "branch": node.branch or "",
          "hash": str(hash),
          "devices": json.dumps(list(node.devices.keys())),
          "volumes": json.dumps(list(node.volumes)),
          "ports": json.dumps(node.ports),
        },
        rm=REMOVE_BUILD_INTERMEDIATES,
        decode=True  # ← auto-decodes each chunk from JSON
      )

      STEP_RE = re.compile(r"Step (\d+/\d+)")

      # Parse the build logs and save into the logs dict
      for chunk in build_stream:
        if "stream" in chunk:
          match = STEP_RE.search(chunk["stream"])
          if match:
            self.build_step[node.name] = match.group(1)
          else:
            line = chunk["stream"].strip()
            if line:
                self.build_logs[node.name].append(line + "\n")
        elif "errorDetail" in chunk:
          detail = chunk["errorDetail"].get("message", "")
          self.build_logs[node.name].append(f"ERROR: {detail}\n")
          raise Exception(detail)
        elif "error" in chunk:
          raise Exception(chunk["error"])
        elif "status" in chunk:
          self.build_logs[node.name].append(chunk["status"] + "\n")
        elif "aux" in chunk:
          self.build_logs[node.name].append(f"Image ID: {chunk['aux'].get('ID', '?')}\n")

      self.build_logs[node.name].append(f"Finished building {node.name}.\n")
      self.build_status[node.name] = "done"

      # Update GUI to show the image is built
      node.image_exists = True

    except Exception as e:
      self.build_logs[node.name].append(f"ERROR: {e}\n")
      self.build_status[node.name] = "error"
      print(e)

  def is_build_running(self, node: TreeNode) -> bool:
    return self.build_status.get(node.name) == "building"

  def get_logs(self, node: TreeNode) -> list[str]:
    return self.build_logs.get(node.name, [])

  def start_container(self) -> None:
    pass

  def _get_docker_client(self) -> docker.DockerClient:
    try:
      client = docker.from_env()
      client.ping()
      return client
    except DockerException:
      raise RuntimeError("Docker is not running. Please start Docker and try again.")

  def check_container_exists(self, name: str) -> tuple[bool, str, Container | None]:
    list = self.client.containers.list(all=True, filters={"name": name})
    if not list:
      return False, "none", None
    
    old_container = list[0]
    old_hash = old_container.labels.get('runtime_hash', None)

    if old_hash == self.runtime_hash:
      if old_container.status == "running":
        return True, "running", old_container
      elif old_container.status == "exited":
        return True, "exited", old_container
      else:
        return False, "error", old_container
    else:
      # Outdated container
      return True, "outdated", old_container
    
  def start_helios(self, tree_path: Path):
    #TODO: Have a dynamic name pulling based on node ID?
    running, status, cont = self.check_container_exists("Helios")

    if status == "error":
      print("Ran into an unknown error. Stopping.")
      return 

    if running == True:
      if status == "running":
        print("Helios container is already running. No additional builds will be run.")
        return
      elif status == "exited":
        print("Helios container is up-to-date. Starting it back up...")
        if not cont == None: cont.restart()
      elif status == "outdated":
        print("Helios container is outdated. Removing it...")
        if not cont == None: cont.remove(force=True)

    mount_volumes = DOCKER_VOLUME_CONFIG | {
        str(tree_path): {
          'bind': '/temp/component_tree.json',
          'mode': 'ro'
        }
      }

    # Bind /dev on linux for automatic udev reconnection
    if platform.system() == "Linux":
      mount_volumes['/dev'] = {'bind': '/dev', 'mode': 'ro'}

    print("Starting a new Helios container...")
    container = self.client.containers.run(
      'helioscore', # TODO: DYNAMIC NAME FROM NODE 
      name='Helios', 
      detach=True,
      volumes=mount_volumes,
      labels={
        'runtime_hash': self.runtime_hash
      },
      entrypoint="./bin/helios",
      command=[
        "-d",
        "--component-tree", "/temp/component_tree.json", #TODO: DYNAMIC PATH
        "-rt", self.runtime_hash
      ]
    )

    time.sleep(2) 
    container.reload()

    if container.status == "running":
      print("Helios is up! Running the next task...")
      print("Shutting down...")
      sys.exit(0)
    else:
      logs = container.logs().decode('utf-8')
      print(f"Container failed to stay up. Status: {container.status}\n")
      print(f"============== Logs ============== \n{logs}")