from pathlib import Path

import yaml


def make_transgene_gtf(yaml_path: str) -> Path:
    """Generate a transgene GTF file from a YAML locus definition.

    The YAML must contain:
      - loci: mapping of locus names to {chrom, start, end, strand}

    The GTF is written to trans.gtf in the same directory as the YAML file.
    """
    yaml_file = Path(yaml_path).expanduser().resolve()
    with open(yaml_file) as fh:
        sitedb = yaml.safe_load(fh)

    trans_gtf_path = yaml_file.parent / "trans.gtf"

    with open(trans_gtf_path, "w") as trans_out:
        for name, locus in sitedb["loci"].items():
            print(f"adding {name}")
            source = "HAVANA"
            chrom = locus["chrom"]
            start = locus["start"]
            end = locus["end"]
            strand = locus["strand"]
            for ann_type in ["CDS", "transcript", "exon"]:
                attrs = (
                    f'gene_id "{name}"; gene_version "1"; '
                    f'transcript_id "{name}"; transcript_version "1"; '
                    f'exon_number "1"; gene_name "{name}"; '
                    f'gene_source "{source}"; gene_biotype "protein_coding"; '
                    f'transcript_name "{name}"; transcript_source "{source}"; '
                    f'transcript_biotype "protein_coding"; '
                    f'protein_id "{name}"; protein_version "3"; tag "basic";'
                )
                line = f"{chrom}\t{source}\t{ann_type}\t{start}\t{end}\t.\t{strand}\t0\t{attrs}"
                trans_out.write(line + "\n")

    print(f"trans annotations saved to {trans_gtf_path}")
    return trans_gtf_path
