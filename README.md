# cr-mkref

Build custom Cell Ranger references with transgene loci.

Wraps the standard `cellranger mkref` pipeline and handles downloading the
mouse genome (GENCODE M23 / GRCm38), filtering annotations, and appending
user-defined transgene FASTA + GTF records.

## Installation

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
cd ~/src/cr-mkref
uv sync
```

All commands are run via `uv run` from the project directory:

```bash
uv run cr-mkref <command>
```

## Workflow overview

![workflow](docs/workflow.svg)

## Prerequisites

Before running `cr-mkref`, you need:

1. **Cell Ranger** installed on your system. Note the full path to the `cellranger` binary.

2. **Transgene FASTA files** — one file per artificial chromosome, placed in a single directory.

### Transgene FASTA requirements

Each transgene sequence lives in its own FASTA file. The build script collects
all files matching `chr*.fa` in the root directory, so:

- **Each FASTA file is referenced by name** in `genrefdb.yaml` via the `fa` field.
  Only files listed in the YAML are included in the reference.
- **The FASTA header determines the chromosome name.** The first word after `>`
  is what Cell Ranger uses as the chromosome. This must match the `chrom` field
  you enter in the wizard.

Example — a transgene on artificial chromosome `chrTrans`:

```
>chrTrans chrTrans
ATCACCTCGAGTTTACTCCCTATCAGTGATAGAGAACGTATG...
```

Here `chrTrans` is the chromosome name. In `genrefdb.yaml`, the corresponding
locus must use `chrom: chrTrans`.

You also need to know the **1-based start and end coordinates** of the gene of
interest within each FASTA sequence, and the **strand** (`+` or `-`). These
define where the GTF annotation records will be placed.

### Example directory layout

```
transgenes/
├── chrTrans.fa      # >chrTrans chrTrans
├── chrCas9.fa       # >chrCas chrCas
└── chrLt.fa         # >chrLt chrLt
```

## Quick start

```bash
cd ~/src/cr-mkref

# 1. Run the wizard to generate config files
uv run cr-mkref init -o my_project/

# 2. Generate the transgene GTF
uv run cr-mkref gtf my_project/

# 3. Build the reference
uv run cr-mkref create my_project/
```

## Commands

### `cr-mkref init`

Interactive TUI wizard that walks through configuration and writes two files:

```
uv run cr-mkref init [--output-dir DIR]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--output-dir`, `-o` | `.` | Directory to write output files |

The wizard has three steps:

**Step 1 — Host configuration**

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| Cell Ranger binary path | yes | — | Full path to `cellranger` binary |
| Reference output directory | yes | — | Where the reference will be built |
| Threads | no | 20 | Threads for `cellranger mkref` |
| Local memory (GB) | no | — | Memory limit for `cellranger mkref` |

**Step 2 — Assembly configuration**

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| Genome name | yes | — | Name for the reference (e.g. `mm10_wlt`) |
| Version | no | `2020-A` | Reference version string |
| Build directory name | no | `mm10_scshRNA_2020-A` | Subdirectory for build artifacts |

**Step 3 — Transgene loci**

| Field | Description |
|-------|-------------|
| Root directory | Directory containing per-chromosome transgene FASTA files (`chr*.fa`) |
| Loci table | Add/remove transgene loci via the interactive table |

Each locus entry requires:

| Field | Example | Description |
|-------|---------|-------------|
| Name | `Egfp-dox` | Gene name used in GTF records |
| Chromosome | `chrTrans` | Must match the FASTA header |
| FASTA filename | `chrTrans.fa` | File within rootdir |
| Start | `383` | 1-based start coordinate |
| End | `1288` | End coordinate |
| Strand | `+` | `+` or `-` |

#### Output files

**`genrefdb.yaml`** — locus definitions consumed by `cr-mkref gtf` and the bash pipeline:

```yaml
rootdir: /path/to/transgenes/
loci:
  Egfp-dox:
    chrom: chrTrans
    fa: XLone-GFP.fa
    start: 383
    end: 1288
    strand: "+"
```

**`cr-mkref.env.sh`** — environment variables for the bash pipeline:

```bash
#!/usr/bin/env bash
export CELLRANGER_BIN="/path/to/cellranger"
export REF_DIR="/path/to/ref_dir"
export GENOME_NAME="mm10_wlt"
export VERSION="2020-A"
export BUILD="mm10_scshRNA_2020-A"
export NTHREADS="20"
export YAML_PATH="/absolute/path/to/genrefdb.yaml"
```

### `cr-mkref gtf`

Generate a transgene GTF from locus definitions in a YAML file.

```
uv run cr-mkref gtf [project_dir]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `project_dir` | `.` | Project directory containing `genrefdb.yaml` |

For each locus, three GTF records are written (CDS, transcript, exon) with
`protein_coding` biotype so Cell Ranger counts them. The output is written to
`trans.gtf` in the same directory as the YAML file.

### `cr-mkref create`

Build the Cell Ranger reference using the config directory generated by `cr-mkref init`.

```
uv run cr-mkref create [project_dir]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `project_dir` | `.` | Project directory containing `cr-mkref.env.sh` |

Looks for `cr-mkref.env.sh` in the given directory, parses its
`export KEY="VALUE"` lines, merges them into the current environment,
and runs `make_custom_ref_mm10.sh`.

### `make_custom_ref_mm10.sh`

Bash pipeline that does the heavy lifting. Called automatically by
`cr-mkref create`. Expects environment variables from `cr-mkref.env.sh`.

What it does:

1. Downloads GRCm38 genome FASTA and GENCODE vM23 GTF (skips if already present)
2. Adjusts chromosome names to `chr*` convention
3. Strips Ensembl version suffixes from gene/transcript/exon IDs
4. Filters annotations to protein-coding, lncRNA, and IG/TR biotypes
5. Appends transgene FASTA and GTF (output of `cr-mkref gtf`)
6. Runs `cellranger mkref`

## Full workflow example

```bash
cd ~/src/cr-mkref

# Generate config interactively
uv run cr-mkref init -o ~/projects/my_experiment/conf/

# Review what was generated
cat ~/projects/my_experiment/conf/genrefdb.yaml
cat ~/projects/my_experiment/conf/cr-mkref.env.sh

# Generate transgene GTF from locus definitions
uv run cr-mkref gtf ~/projects/my_experiment/conf/

# Build the Cell Ranger reference
uv run cr-mkref create ~/projects/my_experiment/conf/
```

## Project structure

```
cr-mkref/
├── pyproject.toml
├── genrefdb.template.yaml        # Example YAML for reference
├── scripts/
│   └── make_custom_ref_mm10.sh   # Main bash pipeline
└── src/cr_mkref/
    ├── __init__.py
    ├── cli.py                    # Argument parsing + subcommands
    ├── create.py                 # cr-mkref create: env parsing + subprocess runner
    ├── gtf.py                    # Transgene GTF generation
    └── tui.py                    # Textual TUI wizard
```
