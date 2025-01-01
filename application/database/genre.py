"""
    Title: Music Collection Manager
    Description: A Python application to manage and enhance a personal music collection.
    Author: Susanna
    License: MIT License
    Created: 2025

    Copyright (c) 2025 Susanna Maria Hepp

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

import json
import re
from collections import Counter, defaultdict

from database.database_helper import create_cursor, execute_query


def split_and_normalize_genres(genre_string):
    # Split by common delimiters: '/', ';', and spaces between genres
    split_genres = re.split(r"[;/]", genre_string)
    # Normalize: trim whitespace and convert to lowercase
    return [genre.strip().lower() for genre in split_genres]


def collect_genres():
    # Example: Replace with your actual list of genres from the database
    cursor = create_cursor()

    SQL_GENRES = "SELECT DISTINCT genre FROM tracks WHERE genre IS NOT NULL;"
    results = execute_query(
        cursor, SQL_GENRES, params="", fetch_one=False, fetch_all=True
    )

    genres = [tup[0] for tup in results]

    normalized_genres = []
    for genre in genres:
        normalized_genres.extend(split_and_normalize_genres(genre))

    # Step 2: Count occurrences of each genre
    genre_counts = Counter(normalized_genres)

    # Step 3: Categorize genres into high-level categories
    genre_tree = defaultdict(list)
    high_level_categories = {
        "pop": ["pop", "dance pop", "synthpop", "pop rock"],
        "rock": ["rock", "alternative rock", "hard rock", "indie rock", "classic rock"],
        "electronic": ["electronic", "house", "trance", "techno", "ambient"],
        "jazz": ["jazz", "smooth jazz", "bebop", "fusion"],
        "classical": ["classical", "baroque", "romantic", "modern"],
        "metal": ["metal", "heavy metal", "death metal", "black metal"],
        # Add more high-level categories as needed
    }

    # Assign genres to categories
    for genre, count in genre_counts.items():
        found = False
        for category, subgenres in high_level_categories.items():
            if genre in subgenres:
                genre_tree[category].append({"genre": genre, "count": count})
                found = True
                break
        if not found:
            genre_tree["uncategorized"].append({"genre": genre, "count": count})

    # Step 4: Save the categorized tree to a file
    with open("genre_tree.json", "w") as f:
        json.dump(genre_tree, f, indent=4)

    print("Genre tree saved to 'genre_tree.json'")
