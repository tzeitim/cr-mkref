import os
import re
import subprocess
import sys
from pathlib import Path


def _parse_env_file(env_path: Path) -> dict[str, str]:
    """Extract KEY=VALUE pairs from a bash export file."""
    env = {}
    pattern = re.compile(r'^export\s+(\w+)=["\']?(.*?)["\']?\s*$')
    for line in env_path.read_text().splitlines():
        m = pattern.match(line)
        if m:
            env[m.group(1)] = os.path.expanduser(m.group(2))
    return env


ENV_FILENAME = "cr-mkref.env.sh"


def run_create(project_dir: str) -> None:
    proj = Path(project_dir).expanduser().resolve()
    if not proj.is_dir():
        print(f"error: directory not found: {project_dir}", file=sys.stderr)
        sys.exit(1)

    env_path = proj / ENV_FILENAME
    if not env_path.is_file():
        print(f"error: {ENV_FILENAME} not found in {proj}", file=sys.stderr)
        sys.exit(1)

    script = Path(__file__).resolve().parent.parent.parent / "scripts" / "make_custom_ref_mm10.sh"
    if not script.is_file():
        print(f"error: build script not found at {script}", file=sys.stderr)
        sys.exit(1)

    merged_env = {**os.environ, **_parse_env_file(env_path)}
    result = subprocess.run(["bash", str(script)], env=merged_env)
    sys.exit(result.returncode)
