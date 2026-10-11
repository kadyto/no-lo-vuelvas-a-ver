import argparse
from pathlib import Path

from app.config import Settings
from app.db import backup


def main():
    parser = argparse.ArgumentParser(description="Herramientas de conservación de No lo vuelvas a ver")
    commands = parser.add_subparsers(dest="command", required=True)
    copy = commands.add_parser("backup", help="Copia consistente mediante la API SQLite; destino nuevo")
    copy.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "backup":
        backup(Settings.from_env().db_path, args.destination)
        print("Copia consistente creada; integrity_check correcto.")


if __name__ == "__main__":
    main()
