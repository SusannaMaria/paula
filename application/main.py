#!/usr/bin/env python
"""
    Title: Music Collection Manager
    Description: A Python application to manage and enhance a personal music collection.
    Author: Susanna
    License: MIT License
    Created: 2024

    Copyright (c) 2024 Susanna Maria Hepp

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.
"""

import sys

from gui.treelist import MusicDatabaseApp
from similarity.similarity_main import run_similarity

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import argparse
from importer.importer_main import run_import
from database.database_helper import (
    backup_database,
    clean_tables,
    close_connection,
    restore_database,
)
from utils.logging_config import setup_logging
import logging

from updater.updater_main import extract_features, run_updater
from search.search_main import run_search
from cover.cover_main import create_mosaic, get_album_covers


def main():

    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        logger.info("Application started")
        # Existing application logic...

        parser = argparse.ArgumentParser(description="Music Database Manager")
        subparsers = parser.add_subparsers(dest="command", required=True)

        subparsers.add_parser("mosaic", help="Creat mosaic from cover images.")
        subparsers.add_parser("gui", help="Use the gui.")
        cover_parser = subparsers.add_parser(
            "cover", help="Get cover images from audio files."
        )

        cover_parser.add_argument(
            "--clean",
            action="store_true",
            help="Remove existing cover files from path before collecting cover from audio file.",
        )
        # Import Command
        import_parser = subparsers.add_parser(
            "import", help="Import metadata from audio files."
        )
        import_parser.add_argument(
            "directory", help="Directory containing audio files to import."
        )
        import_parser.add_argument(
            "--retry-errors",
            action="store_true",
            help="Retry files with status = 'error'.",
        )

        import_parser.add_argument(
            "--clean", action="store_true", help="Clean the database before import."
        )

        # Update Command
        update_parser = subparsers.add_parser(
            "update", help="Update database using MusicBrainz."
        )
        update_parser.add_argument(
            "--type",
            choices=["artists", "albums", "tracks", "all"],
            help="Specify what to update: artists, albums, tracks or all.",
            required=False,
            default="all",
        )
        update_parser.add_argument(
            "--retry-errors",
            action="store_true",
            help="Retry files with status = 'error'.",
        )
        update_parser.add_argument(
            "--update-valid-entries",
            action="store_true",
            help="Update valid entries",
        )
        update_parser.add_argument(
            "--extract-features",
            action="store_true",
            help="Update valid entries",
        )
        # Search Command
        search_parser = subparsers.add_parser(
            "search", help="Search music in the database."
        )
        search_parser.add_argument(
            "--query", help="Search query (e.g., 'artist: Tool and genre: Rock')."
        )
        subparsers.add_parser("backup", help="Backup database into file")
        subparsers.add_parser("restore", help="Restore database from file")

        similarity_parser = subparsers.add_parser(
            "similarity", help="Compute simularity based on song features."
        )
        similarity_parser.add_argument(
            "--normalize",
            action="store_true",
            help="Normalize features and store it in json in db",
        )
        similarity_parser.add_argument(
            "--train",
            action="store_true",
            help="Train weights based on user feedback",
        )
        similarity_parser.add_argument(
            "--query",
            help="Search query (e.g., 'artist: Tool and genre: Rock').",
            default=None,
            required=False,
        )

        args = parser.parse_args()

        if args.command == "import":
            if args.clean:
                logger.info("Cleaning the database...")
                clean_tables()
            run_import(args.directory, retry_errors=args.retry_errors)

        elif args.command == "update":
            if args.extract_features:
                extract_features()
            else:
                run_updater(
                    args.type,
                    retry_errors=args.retry_errors,
                    update_valid_entries=args.update_valid_entries,
                    extract_features=args.extract_features,
                )
        elif args.command == "search":
            run_search(args.query)
        elif args.command == "mosaic":
            create_mosaic()
        elif args.command == "cover":
            get_album_covers(perform_action=True, remove_existing=args.clean)
        elif args.command == "backup":
            backup_file = backup_database()
            if backup_file:
                print(f"Database backed up successfully to {backup_file}.")
        elif args.command == "restore":
            backup_file = input("Enter the path to the backup file: ")
            restore_database(backup_file=backup_file)
        elif args.command == "similarity":
            run_similarity(
                do_normalize=args.normalize, input_query=args.query, do_train=args.train
            )
        elif args.command == "gui":
            MusicDatabaseApp().run()

        close_connection()
    except Exception as e:
        logger.exception("Unhandled exception occurred")
    finally:
        logger.info("Application exiting")


if __name__ == "__main__":
    main()
