import random
from statistics import mean
from textual.containers import Container, Vertical, Horizontal
from textual.app import App, ComposeResult, RenderResult
from textual.widgets import Sparkline, Static, Label, Sparkline, OptionList
from textual.widget import Widget
from textual.widgets.option_list import Option
import sqlite3

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
