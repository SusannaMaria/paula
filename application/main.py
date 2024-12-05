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

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import argparse
from importer.importer_main import run_import
from database.database_helper import clean_tables, close_connection
from logging_config import setup_logging
import logging

# from updater.updater_main import run_update
from search.search_main import run_search


def main():

    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        logger.info("Application started")
        # Existing application logic...

        parser = argparse.ArgumentParser(description="Music Database Manager")
        subparsers = parser.add_subparsers(dest="command", required=True)

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

        # # Update Command
        # update_parser = subparsers.add_parser("update", help="Update database using MusicBrainz.")

        # # Search Command
        search_parser = subparsers.add_parser(
            "search", help="Search music in the database."
        )
        search_parser.add_argument(
            "query", help="Search query (e.g., 'artist: Tool and genre: Rock')."
        )

        args = parser.parse_args()

        if args.command == "import":
            if args.clean:
                logger.info("Cleaning the database...")
                clean_tables()
            run_import(args.directory, retry_errors=args.retry_errors)

        # elif args.command == "update":
        #     run_update()
        elif args.command == "search":
            run_search(args.query)

        close_connection()
    except Exception as e:
        logger.exception("Unhandled exception occurred")
    finally:
        logger.info("Application exiting")


if __name__ == "__main__":
    main()
