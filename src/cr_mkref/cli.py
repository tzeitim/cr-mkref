import argparse
import sys

from cr_mkref.gtf import make_transgene_gtf


def cmd_gtf(args):
    make_transgene_gtf(args.yaml_path)


def cmd_init(args):
    from cr_mkref.tui import run_wizard

    run_wizard(output_dir=args.output_dir)


def cmd_create(args):
    from cr_mkref.create import run_create

    run_create(args.project_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cr-mkref", description="Cell Ranger reference builder utilities")
    sub = parser.add_subparsers(dest="command")

    gtf_parser = sub.add_parser("gtf", help="Generate transgene GTF from a YAML locus definition")
    gtf_parser.add_argument("yaml_path", help="Path to the genrefdb YAML file")

    init_parser = sub.add_parser("init", help="Interactive wizard to create config files")
    init_parser.add_argument("--output-dir", "-o", default=".", help="Directory to write output files")

    create_parser = sub.add_parser("create", help="Build the Cell Ranger reference")
    create_parser.add_argument("project_dir", help="Project directory containing cr-mkref.env.sh")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "gtf":
        cmd_gtf(args)
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "create":
        cmd_create(args)


if __name__ == "__main__":
    main()
