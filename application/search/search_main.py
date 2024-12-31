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

import logging
import re

from database.database_helper import execute_query_print_out
from utils.config_loader import load_config

logger = logging.getLogger(__name__)
# Load configuration
config = load_config()

# Field mapping
FIELD_MAP = {
    "artist": "artists.name",
    "genre": "tracks.genre",
    "album": "albums.name",
    "title": "tracks.title",
}


def parse_query(input_query):
    logical_operator = "AND"
    conditions = []

    for part in re.split(r"\s+(and|or)\s+", input_query, flags=re.IGNORECASE):
        if part.lower() in {"and", "or"}:
            logical_operator = part.upper()
        else:
            match = re.match(r"(\w+):\s*(.+)", part.strip())
            if match:
                field, value = match.groups()
                field = field.lower()
                if field in FIELD_MAP:
                    conditions.append((FIELD_MAP[field], value))
    return conditions, logical_operator


def build_sql_query(conditions, logical_operator):
    where_clauses = []
    params = []

    for field, value in conditions:
        where_clauses.append(f"{field} LIKE ?")
        params.append(f"%{value}%")

    where_clause = f" {logical_operator} ".join(where_clauses)
    sql_query = f"""
        SELECT tracks.track_id, tracks.title, artists.artist_id, artists.name AS artist, albums.name AS album, tracks.genre
        FROM tracks
        JOIN artists ON tracks.artist_id = artists.artist_id
        JOIN albums ON tracks.album_id = albums.album_id
        WHERE {where_clause};
    """
    return sql_query, params


def create_search_query(input_query):
    conditions, logical_operator = parse_query(input_query)
    sql_query, params = build_sql_query(conditions, logical_operator)
    return (sql_query, params)


def run_search(input_query):
    logger.info(f"Search initiated with query: {input_query}")
    try:
        sql_query, params = create_search_query(input_query)
        logger.info(f"Generated SQL Query: {sql_query}")
        logger.info(f"Parameters: {params}")
        execute_query_print_out(sql_query, params)
    except Exception as e:
        logger.error(f"Search failed: {e}")
