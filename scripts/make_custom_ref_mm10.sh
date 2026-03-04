#!/usr/bin/env bash
set -euo pipefail

# ── Required variables (set before sourcing or export from env) ──────────────
: "${YAML_PATH:?YAML_PATH is required (path to genrefdb.yaml)}"
: "${CELLRANGER_BIN:?CELLRANGER_BIN is required (path to cellranger binary)}"
: "${GENOME_NAME:?GENOME_NAME is required (e.g. mm10_wlt or mm10_carlin)}"

# ── Optional variables ───────────────────────────────────────────────────────
REF_DIR="${REF_DIR:-$(pwd)}"
VERSION="${VERSION:-2020-A}"
BUILD="${BUILD:-mm10_scshRNA_2020-A}"
NTHREADS="${NTHREADS:-20}"
LOCALMEM="${LOCALMEM:-}"

if [ ! -d "$REF_DIR" ]; then
	echo "made ref dir $REF_DIR"
	mkdir -p "$REF_DIR"
fi

cd "$REF_DIR"

# Set up source and build directories
mkdir -p "$BUILD"

# Download source files if they do not exist in reference_sources/ folder
source="reference_sources"
mkdir -p "$source"

fasta_url="https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_mouse/release_M23/GRCm38.primary_assembly.genome.fa.gz"
fasta_in="${source}/GRCm38.primary_assembly.genome.fa.gz"

gtf_url="https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_mouse/release_M23/gencode.vM23.annotation.gtf.gz"
gtf_in="${source}/gencode.vM23.annotation.gtf"

if [ ! -f "temp_fasta.gz" ]; then
    echo "downloading genome"
    curl -S "$fasta_url" -o temp_fasta.gz
else
    echo "temp_fasta.gz already exists."
fi

if [ ! -f "$fasta_in" ]; then
    echo "unzipping genome"
    zcat temp_fasta.gz > "$fasta_in"
else
    echo "File $fasta_in already exists."
fi

if [ ! -f "temp_gtf.gz" ]; then
    echo "downloading annotations"
    curl -S "$gtf_url" -o temp_gtf.gz
else
    echo "temp_gtf.gz already exists."
fi

if [ ! -f "$gtf_in" ]; then
    echo "unzipping annotations"
    zcat temp_gtf.gz > "$gtf_in"
else
    echo "File $gtf_in already exists."
fi


# Modify sequence headers in the Ensembl FASTA to match the file
# "GRCh38.primary_assembly.genome.fa" from GENCODE. Unplaced and unlocalized
# sequences such as "KI270728.1" have the same names in both versions.
#
# Input FASTA:
#   >1 dna:chromosome chromosome:GRCh38:1:1:248956422:1 REF
#
# Output FASTA:
#   >chr1 1
fasta_modified="$BUILD/$(basename "$fasta_in").modified"
# sed commands:
# 1. Replace metadata after space with original contig name, as in GENCODE
# 2. Add "chr" to names of autosomes and sex chromosomes
# 3. Handle the mitochrondrial chromosome
echo "adjusting ref names from $fasta_in"

cat "$fasta_in" \
    | sed -E 's/^>(\S+).*/>\1 \1/' \
    | sed -E 's/^>([0-9]+|[XY]) />chr\1 /' \
    | sed -E 's/^>MT />chrM /' \
    > "$fasta_modified"


# Remove version suffix from transcript, gene, and exon IDs in order to match
# previous Cell Ranger reference packages
#
# Input GTF:
#     ... gene_id "ENSG00000223972.5"; ...
# Output GTF:
#     ... gene_id "ENSG00000223972"; gene_version "5"; ...
gtf_modified="$BUILD/$(basename "$gtf_in").modified"
# Pattern matches Ensembl gene, transcript, and exon IDs for human or mouse:
echo "adjusting ann names"

ID="(ENS(MUS)?[GTE][0-9]+)\.([0-9]+)"
cat "$gtf_in" \
    | sed -E 's/gene_id "'"$ID"'";/gene_id "\1"; gene_version "\3";/' \
    | sed -E 's/transcript_id "'"$ID"'";/transcript_id "\1"; transcript_version "\3";/' \
    | sed -E 's/exon_id "'"$ID"'";/exon_id "\1"; exon_version "\3";/' \
    > "$gtf_modified"


# Define string patterns for GTF tags
# NOTES:
# - Since GENCODE release 31/M22 (Ensembl 97), the "lincRNA" and "antisense"
#   biotypes are part of a more generic "lncRNA" biotype.
# - These filters are relevant only to GTF files from GENCODE. The GTFs from
#   Ensembl release 98 have the following differences:
#   - The names "gene_biotype" and "transcript_biotype" are used instead of
#     "gene_type" and "transcript_type".
#   - Readthrough transcripts are present but are not marked with the
#     "readthrough_transcript" tag.
#   - Only the X chromosome versions of genes in the pseudoautosomal regions
#     are present, so there is no "PAR" tag.
BIOTYPE_PATTERN=\
"(protein_coding|lncRNA|\
IG_C_gene|IG_D_gene|IG_J_gene|IG_LV_gene|IG_V_gene|\
IG_V_pseudogene|IG_J_pseudogene|IG_C_pseudogene|\
TR_C_gene|TR_D_gene|TR_J_gene|TR_V_gene|\
TR_V_pseudogene|TR_J_pseudogene)"
GENE_PATTERN="gene_type \"${BIOTYPE_PATTERN}\""
TX_PATTERN="transcript_type \"${BIOTYPE_PATTERN}\""
READTHROUGH_PATTERN="tag \"readthrough_transcript\""
PAR_PATTERN="tag \"PAR\""


# Construct the gene ID allowlist. We filter the list of all transcripts
# based on these criteria:
#   - allowable gene_type (biotype)
#   - allowable transcript_type (biotype)
#   - no "PAR" tag (only present for Y chromosome PAR)
#   - no "readthrough_transcript" tag
# We then collect the list of gene IDs that have at least one associated
# transcript passing the filters.
echo "constructing allowlist"

cat "$gtf_modified" \
    | awk '$3 == "transcript"' \
    | grep -E "$GENE_PATTERN" \
    | grep -E "$TX_PATTERN" \
    | grep -Ev "$READTHROUGH_PATTERN" \
    | grep -Ev "$PAR_PATTERN" \
    | sed -E 's/.*(gene_id "[^"]+").*/\1/' \
    | sort \
    | uniq \
    > "${BUILD}/gene_allowlist"


# Filter the GTF file based on the gene allowlist
gtf_filtered="${BUILD}/$(basename "$gtf_in").filtered"
# Copy header lines beginning with "#"
echo "filtering GTF"
grep -E "^#" "$gtf_modified" > "$gtf_filtered"
# Filter to the gene allowlist
grep -Ff "${BUILD}/gene_allowlist" "$gtf_modified" \
    >> "$gtf_filtered"

# Generate transgene fasta (assumes yaml)
TRANS_DB=$(grep rootdir "$YAML_PATH" | awk '{print $2}')
TRANS_DB="${TRANS_DB/#\~/$HOME}"
TRANS_FA="$TRANS_DB"/trans.fa

echo "loading transgene data from $YAML_PATH"
# Append transgene fastas to $fasta_modified
cat "$TRANS_DB"/chr*.fa > "$TRANS_FA"
cat "$TRANS_FA" >> "$fasta_modified"

echo "$TRANS_FA"
echo "$fasta_modified"

echo "Transgenes added:"
grep -P ">" "$TRANS_FA"

# Append custom GTF to final one (generated by cr-mkref gtf)
TRANS_GTF=$(grep trans_gtf "$YAML_PATH" | awk '{print $2}')
TRANS_GTF="${TRANS_GTF/#\~/$HOME}"
echo "loading annotation data from $TRANS_GTF"
cat "$TRANS_GTF" >> "$gtf_filtered"

# Build cellranger mkref arguments
mkref_args=(
    --ref-version="$VERSION"
    --genome="$GENOME_NAME"
    --fasta="$fasta_modified"
    --genes="$gtf_filtered"
    --nthreads="$NTHREADS"
)

if [ -n "$LOCALMEM" ]; then
    mkref_args+=(--localmem="$LOCALMEM")
fi

# Create reference package
echo "running cell ranger mkref"
$CELLRANGER_BIN mkref "${mkref_args[@]}"
