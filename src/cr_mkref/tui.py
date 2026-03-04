from __future__ import annotations

import os
from pathlib import Path

import yaml
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Static,
)

# ---------------------------------------------------------------------------
# Locus modal
# ---------------------------------------------------------------------------

class LocusModal(ModalScreen[dict | None]):
    CSS = """
    LocusModal {
        align: center middle;
    }
    #locus-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        border: thick $accent;
        background: $surface;
    }
    #locus-dialog Label {
        margin-top: 1;
    }
    #locus-buttons {
        margin-top: 1;
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="locus-dialog"):
            yield Label("Add Locus")
            yield Label("Name")
            yield Input(id="loc-name", placeholder="e.g. Egfp-dox")
            yield Label("Chromosome")
            yield Input(id="loc-chrom", placeholder="e.g. chrTrans")
            yield Label("FASTA filename")
            yield Input(id="loc-fa", placeholder="e.g. chrTrans.fa")
            yield Label("Start")
            yield Input(id="loc-start", placeholder="e.g. 383", type="integer")
            yield Label("End")
            yield Input(id="loc-end", placeholder="e.g. 1288", type="integer")
            yield Label("Strand")
            yield Input(id="loc-strand", placeholder="+ or -", value="+")
            with Horizontal(id="locus-buttons"):
                yield Button("OK", variant="primary", id="loc-ok")
                yield Button("Cancel", id="loc-cancel")

    @on(Button.Pressed, "#loc-ok")
    def _ok(self) -> None:
        name = self.query_one("#loc-name", Input).value.strip()
        if not name:
            self.notify("Name is required", severity="error")
            return
        self.dismiss(
            {
                "name": name,
                "chrom": self.query_one("#loc-chrom", Input).value.strip(),
                "fa": self.query_one("#loc-fa", Input).value.strip(),
                "start": int(self.query_one("#loc-start", Input).value or "0"),
                "end": int(self.query_one("#loc-end", Input).value or "0"),
                "strand": self.query_one("#loc-strand", Input).value.strip() or "+",
            }
        )

    @on(Button.Pressed, "#loc-cancel")
    def _cancel(self) -> None:
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Wizard app
# ---------------------------------------------------------------------------

STEP_IDS = ("step-host", "step-assembly", "step-loci")


class WizardApp(App):
    TITLE = "cr-mkref init"
    BINDINGS = [
        ("escape", "quit", "Quit"),
    ]

    CSS = """
    .step { display: none; padding: 1 2; }
    .step.active { display: block; }
    #nav { height: auto; margin-top: 1; dock: bottom; }
    .step Label { margin-top: 1; }
    #loci-table { height: 10; }
    #loci-buttons { height: auto; }
    """

    def __init__(self, output_dir: str = ".") -> None:
        super().__init__()
        self.output_dir = Path(output_dir)
        self.loci: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header()

        # Step 1 — Host config
        with Container(id="step-host", classes="step active"):
            yield Static("Step 1 / 3 — Host configuration", classes="title")
            yield Label("Cell Ranger binary path (required)")
            yield Input(id="cellranger-bin", placeholder="/path/to/cellranger")
            yield Label("Reference output directory (required)")
            yield Input(id="ref-dir", placeholder="/path/to/ref_dir")
            yield Label("Threads")
            yield Input(id="nthreads", value="20", type="integer")
            yield Label("Local memory (GB, optional)")
            yield Input(id="localmem", placeholder="e.g. 64", type="integer")

        # Step 2 — Assembly config
        with Container(id="step-assembly", classes="step"):
            yield Static("Step 2 / 3 — Assembly configuration", classes="title")
            yield Label("Genome name (required)")
            yield Input(id="genome-name", placeholder="e.g. mm10_wlt")
            yield Label("Version")
            yield Input(id="version", value="2020-A")
            yield Label("Build directory name")
            yield Input(id="build", value="mm10_scshRNA_2020-A")

        # Step 3 — Transgene loci
        with Container(id="step-loci", classes="step"):
            yield Static("Step 3 / 3 — Transgene loci", classes="title")
            yield Label("Root directory for transgene FASTAs")
            yield Input(id="rootdir", placeholder="/path/to/transgenes/")
            yield DataTable(id="loci-table")
            with Horizontal(id="loci-buttons"):
                yield Button("Add locus", id="btn-add")
                yield Button("Remove selected", id="btn-remove")

        # Navigation
        with Horizontal(id="nav"):
            yield Button("Back", id="btn-back")
            yield Button("Next", variant="primary", id="btn-next")

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#loci-table", DataTable)
        table.add_columns("Name", "Chrom", "FA", "Start", "End", "Strand")
        self._current_step = 0
        self._update_nav()

    # -- step navigation -----------------------------------------------------

    def _show_step(self, idx: int) -> None:
        for i, sid in enumerate(STEP_IDS):
            container = self.query_one(f"#{sid}")
            if i == idx:
                container.add_class("active")
            else:
                container.remove_class("active")
        self._current_step = idx
        self._update_nav()

    def _update_nav(self) -> None:
        self.query_one("#btn-back", Button).disabled = self._current_step == 0
        btn_next = self.query_one("#btn-next", Button)
        if self._current_step == len(STEP_IDS) - 1:
            btn_next.label = "Finish"
        else:
            btn_next.label = "Next"

    @on(Button.Pressed, "#btn-next")
    def _next(self) -> None:
        if self._current_step < len(STEP_IDS) - 1:
            self._show_step(self._current_step + 1)
        else:
            self._finish()

    @on(Button.Pressed, "#btn-back")
    def _back(self) -> None:
        if self._current_step > 0:
            self._show_step(self._current_step - 1)

    # -- loci management -----------------------------------------------------

    @on(Button.Pressed, "#btn-add")
    def _add_locus(self) -> None:
        self.push_screen(LocusModal(), callback=self._on_locus_result)

    def _on_locus_result(self, result: dict | None) -> None:
        if result is None:
            return
        self.loci.append(result)
        table = self.query_one("#loci-table", DataTable)
        table.add_row(
            result["name"],
            result["chrom"],
            result["fa"],
            str(result["start"]),
            str(result["end"]),
            result["strand"],
        )

    @on(Button.Pressed, "#btn-remove")
    def _remove_locus(self) -> None:
        table = self.query_one("#loci-table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.loci):
            idx = table.cursor_row
            row_key = table.ordered_rows[idx].key
            table.remove_row(row_key)
            self.loci.pop(idx)

    # -- finish & write ------------------------------------------------------

    def _val(self, selector: str) -> str:
        return self.query_one(selector, Input).value.strip()

    def _finish(self) -> None:
        missing = []
        if not self._val("#cellranger-bin"):
            missing.append("Cell Ranger binary path")
        if not self._val("#ref-dir"):
            missing.append("Reference output directory")
        if not self._val("#genome-name"):
            missing.append("Genome name")
        if missing:
            self.notify("Missing required fields: " + ", ".join(missing), severity="error")
            return
        self._write_outputs()
        self.exit()

    def _write_outputs(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # --- genrefdb.yaml ---
        rootdir = os.path.expanduser(self._val("#rootdir"))
        loci_dict = {}
        for loc in self.loci:
            loci_dict[loc["name"]] = {
                "chrom": loc["chrom"],
                "fa": loc["fa"],
                "start": loc["start"],
                "end": loc["end"],
                "strand": loc["strand"],
            }
        yaml_data = {"rootdir": rootdir, "loci": loci_dict}
        yaml_path = self.output_dir / "genrefdb.yaml"
        with open(yaml_path, "w") as fh:
            yaml.dump(yaml_data, fh, default_flow_style=False, sort_keys=False)

        # --- cr-mkref.env.sh ---
        env_path = self.output_dir / "cr-mkref.env.sh"
        lines = [
            "#!/usr/bin/env bash",
            f'export CELLRANGER_BIN="{os.path.expanduser(self._val("#cellranger-bin"))}"',
            f'export REF_DIR="{os.path.expanduser(self._val("#ref-dir"))}"',
            f'export GENOME_NAME="{self._val("#genome-name")}"',
            f'export VERSION="{self._val("#version")}"',
            f'export BUILD="{self._val("#build")}"',
            f'export NTHREADS="{self._val("#nthreads") or "20"}"',
            f'export YAML_PATH="{yaml_path.resolve()}"',
        ]
        localmem = self._val("#localmem")
        if localmem:
            lines.append(f'export LOCALMEM="{localmem}"')
        with open(env_path, "w") as fh:
            fh.write("\n".join(lines) + "\n")

        self._written_yaml = yaml_path.resolve()
        self._written_env = env_path.resolve()


def run_wizard(output_dir: str = ".") -> None:
    app = WizardApp(output_dir=output_dir)
    app.run()

    yaml_path = getattr(app, "_written_yaml", None)
    env_path = getattr(app, "_written_env", None)
    if not yaml_path:
        return

    out_dir = yaml_path.parent
    print(f"\nWrote config to {out_dir}/\n")
    print(f"  {yaml_path.name:<20s}  Transgene locus definitions")
    print(f"  {env_path.name:<20s}  Environment variables for the build\n")
    print("Next steps:\n")
    print(f"  1. Review the generated files")
    print(f"  2. Generate the transgene GTF:")
    print(f"       uv run cr-mkref gtf {yaml_path}")
    print(f"  3. Build the Cell Ranger reference:")
    print(f"       uv run cr-mkref create {out_dir}/")
    print()
