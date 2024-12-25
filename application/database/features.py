import sqlite3

# Connect to the database
database_path = "../database/paula.sqlite"
connection = sqlite3.connect(database_path)
cursor = connection.cursor()
import numpy as np


def check_table(table_name):
    cursor.execute(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';"
    )
    table_exists = cursor.fetchone()
    if table_exists:
        # Step 2: Empty the table
        cursor.execute(f"DELETE FROM {table_name};")
        print(f"Table '{table_name}' has been emptied.")
    else:
        print(f"Table '{table_name}' does not exist, it will be created now.")
        # Create the table
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS feature_distribution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature_name TEXT NOT NULL,
            range_start REAL NOT NULL,
            range_end REAL NOT NULL,
            count INTEGER NOT NULL
        );
        """
        )


table_name = "feature_distribution"
check_table(table_name)

# Features to analyze
features = [
    "danceability",
    "female",
    "male",
    "genre_alternative",
    "genre_blues",
    "genre_electronic",
    "genre_folkcountry",
    "genre_funksoulrnb",
    "genre_jazz",
    "genre_pop",
    "genre_raphiphop",
    "genre_rock",
    "genre_electronic_ambient",
    "genre_electronic_dnb",
    "genre_electronic_house",
    "genre_electronic_techno",
    "genre_electronic_trance",
    "genre_rosamerica_cla",
    "genre_rosamerica_dan",
    "genre_rosamerica_hip",
    "genre_rosamerica_jaz",
    "genre_rosamerica_pop",
    "genre_rosamerica_rhy",
    "genre_rosamerica_roc",
    "genre_rosamerica_spe",
    "genre_tzanetakis_blu",
    "genre_tzanetakis",
    "genre_tzanetakis_cou",
    "genre_tzanetakis_dis",
    "genre_tzanetakis_hip",
    "genre_tzanetakis_jaz",
    "genre_tzanetakis_met",
    "genre_tzanetakis_pop",
    "genre_tzanetakis_reg",
    "genre_tzanetakis_roc",
    "ismir04_rhythm_chachacha",
    "ismir04_rhythm_jive",
    "ismir04_rhythm_quickstep",
    "ismir04_rhythm_rumba_american",
    "ismir04_rhythm_rumba_international",
    "ismir04_rhythm_rumba_misc",
    "ismir04_rhythm_samba",
    "ismir04_rhythm_tango",
    "ismir04_rhythm_viennesewaltz",
    "ismir04_rhythm_waltz",
    "mood_acoustic",
    "mood_electronic",
    "mood_happy",
    "mood_party",
    "mood_relaxed",
    "mood_sad",
    "moods_mirex",
    "timbre",
    "tonal_atonal",
    "voice_instrumental",
    "average_loudness",
    "dynamic_complexity",
    "bpm",
    "chords_key",
    "chords_number_rate",
    "chords_scale",
    "danceability_low",
    "mood_mirex_cluster",
    "mood_mirex_probability",
    "mood_mirex_cluster1",
    "mood_mirex_cluster2",
    "mood_mirex_cluster3",
    "mood_mirex_cluster4",
    "mood_mirex_cluster5",
]

filtered_features = []
feature_min_max = {}

for feature in features:
    query = f"SELECT MIN({feature}), MAX({feature}) FROM track_features;"
    cursor.execute(query)
    feature_min, feature_max = cursor.fetchone()
    if feature_min and feature_max:
        if isinstance(feature_min, (int, float)) and not isinstance(feature_min, str):
            if isinstance(feature_max, (int, float)) and not isinstance(
                feature_max, str
            ):
                mean = (feature_min * feature_max) / 2
                filtered_features.append(feature)
                feature_min_max[feature] = (feature_min, feature_max)

# Number of intervals
interval_count = 100
interval_size = 1 / interval_count
distributions = {}

for feature in filtered_features:
    feature_min, feature_max = feature_min_max[feature]
    results = []

    for i in range(interval_count):
        lower_bound = i * interval_size
        upper_bound = lower_bound + interval_size

        # Convert normalized bounds to original scale
        original_lower = lower_bound * (feature_max - feature_min) + feature_min
        original_upper = upper_bound * (feature_max - feature_min) + feature_min

        # Query to count normalized values
        query = f"""
        SELECT COUNT(*)
        FROM track_features
        WHERE {feature} >= ? AND {feature} < ?;
        """
        cursor.execute(query, (original_lower, original_upper))
        count = cursor.fetchone()[0]

        results.append(count)

        # Insert the distribution into the table
        cursor.execute(
            """
        INSERT INTO feature_distribution (feature_name, range_start, range_end, count)
        VALUES (?, ?, ?, ?);
        """,
            (feature, original_lower, original_upper, count),
        )

# Commit the changes and close the connection
connection.commit()
connection.close()

print("Feature distributions have been calculated and stored!")
