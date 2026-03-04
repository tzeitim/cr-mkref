import os
import re
import subprocess
import sys
from pathlib import Path

import yaml


def _parse_env_file(env_path: Path) -> dict[str, str]:
    """Extract KEY=VALUE pairs from a bash export file."""
    env = {}
    pattern = re.compile(r'^export\s+(\w+)=["\']?(.*?)["\']?\s*$')
    for line in env_path.read_text().splitlines():
        m = pattern.match(line)
        if m:
            env[m.group(1)] = os.path.expanduser(m.group(2))
    return env


def _build_trans_fa(yaml_path: Path) -> Path:
    """Concatenate transgene FASTAs listed in genrefdb.yaml into trans.fa."""
    with open(yaml_path) as fh:
        cfg = yaml.safe_load(fh)

    rootdir = Path(os.path.expanduser(cfg["rootdir"]))
    if not rootdir.is_dir():
        print(f"error: rootdir not found: {rootdir}", file=sys.stderr)
        sys.exit(1)

    fa_files = []
    for name, locus in cfg["loci"].items():
        fa = rootdir / locus["fa"]
        if not fa.is_file():
            print(f"error: FASTA for locus '{name}' not found: {fa}", file=sys.stderr)
            sys.exit(1)
        fa_files.append(fa)

    trans_fa = rootdir / "trans.fa"
    with open(trans_fa, "wb") as out:
        for fa in fa_files:
            out.write(fa.read_bytes())

    print(f"concatenated {len(fa_files)} FASTA file(s) into {trans_fa}")
    return trans_fa


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

    yaml_path = Path(merged_env["YAML_PATH"])
    trans_fa = _build_trans_fa(yaml_path)
    merged_env["TRANS_FA"] = str(trans_fa)

    result = subprocess.run(["bash", str(script)], env=merged_env)
    sys.exit(result.returncode)
