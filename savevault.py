import argparse
import json
import zipfile

from vault import list_snapshots, restore, snapshot, verify


def main():
    parser = argparse.ArgumentParser(description="Keep local game save snapshots")
    parser.add_argument("--vault", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("source")
    backup.add_argument("--label", default="")
    backup.add_argument("--exclude", action="append", default=[])
    commands.add_parser("list")
    check = commands.add_parser("verify")
    check.add_argument("identifier")
    recover = commands.add_parser("restore")
    recover.add_argument("identifier")
    recover.add_argument("destination")
    args = parser.parse_args()
    try:
        if args.command == "backup":
            result = {"id": snapshot(args.source, args.vault, args.label, args.exclude)}
        elif args.command == "list":
            result = list_snapshots(args.vault)
        elif args.command == "verify":
            result = {"files": len(verify(args.vault, args.identifier)["files"])}
        else:
            result = {"restored": restore(args.vault, args.identifier, args.destination)}
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
