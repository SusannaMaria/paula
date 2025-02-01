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

import random
import sqlite3
from statistics import mean

from application.textual.app import App, ComposeResult, RenderResult
from application.textual.containers import Container, Horizontal, Vertical
from application.textual.widget import Widget
from application.textual.widgets import Label, OptionList, Sparkline, Static
from application.textual.widgets.option_list import Option

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

# Connect to the database
database_path = "../database/paula.sqlite"
connection = sqlite3.connect(database_path)
cursor = connection.cursor()


def distribution_of_feature(feature):
    sql = "SELECT count FROM feature_distribution WHERE feature_name = ?;"
    cursor.execute(
        sql,
        (feature,),
    )
    results = cursor.fetchall()

    return [tup[0] for tup in results]


class SparklineSummaryFunctionApp(App[None]):
    CSS_PATH = "features_gui.tcss"

    def compose(self) -> ComposeResult:
        for feature in features:
            data = distribution_of_feature(feature)
            yield Label(feature)
            yield Sparkline(data=data, summary_function=max)
        connection.close()


app = SparklineSummaryFunctionApp()
if __name__ == "__main__":
    app.run()
