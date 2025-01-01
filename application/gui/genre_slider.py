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

import sqlite3

from textual import on
from textual.app import App, ComposeResult
from textual.color import Color
from textual.containers import Horizontal, Vertical
from textual.events import MouseUp
from textual.widget import Widget
from textual.widgets import Label, OptionList, Sparkline
from textual.widgets.option_list import Option
from textual_slider import Slider

from gui.events import CustomClickEvent


class MySlider(Slider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_click(self, event) -> None:
        self.parent.parent.parent.parent.send_event()


class GenreSliders(Widget):
    CSS = """
    Screen {
        align: center middle;
    }

    Horizontal {
        height: auto;
        padding: 0 0 0 0;
        margin: 0;
        border: hidden;
    }
    OptionList {
        border:hidden;
        
    }

    Slider {
        border:hidden;
        padding:0 0 0 0;
    }
    .quote {
        text-style: italic;
    }

    #lbl1 {
        background: red 30%;
        text-style: bold;
    }

    """

    def on_show(self) -> None:
        self.send_event()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.genre_values = {
            "alternative": 0.5,
            "blues": 0.5,
            "electronic": 0.5,
            "folkcountry": 0.5,
            "funksoulrnb": 0.5,
            "jazz": 0.5,
            "pop": 0.5,
            "raphiphop": 0.5,
            "rock": 0.5,
        }
        self.styles.border = ("tall", "#008080")
        self.styles.height = "20"
        self.styles.width = "40"
        self.selected_genre = None
        self.selected_value = 0.5

    def send_event(self):
        ol_i = self.query_one("#genre-option-list").highlighted
        genre = self.query_one("#genre-option-list").get_option_at_index(ol_i).prompt
        value = self.genre_values[genre]
        self.post_message(
            CustomClickEvent(
                self,
                "Genre selected",
                genre,
                max((value * 100 - 3) / 100, 0.0),
                min((value * 100 + 3) / 100, 1.0),
            )
        )

    def on_mouse_up(self, event: MouseUp) -> None:
        self.send_event()

    def compose(self) -> ComposeResult:
        genre_array = list(self.genre_values.keys())
        options = []
        for index, option in enumerate(genre_array):
            options.append(Option(f"{option}", id=f"id-{option}"))
        option_list = OptionList(*options, id="genre-option-list")
        yield option_list
        yield Horizontal(id="dynamic-widget-placeholder")

    @on(Slider.Changed)
    def on_slider_changed(self, event: Slider.Changed) -> None:
        """Handle changes for any slider."""
        # Determine the slider ID
        slider_id = event.slider.id
        value = event.value / 100

        # Construct the corresponding label ID
        label_id = f"{slider_id}-label"
        # Find the label widget and update it
        label = self.query_one(f"#{label_id}", Label)
        genre = str(label_id).replace("-amp-label", "")
        self.selected_genre = genre

        self.genre_values[genre] = value

        self.selected_value = value
        min_value = max((value * 100 - 3) / 100, 0.0)
        max_value = min((value * 100 + 3) / 100, 1.0)
        label.update(f"{min_value}\n-\n{max_value}")
        event.slider.styles.background = Color(value * 255, value * 255, value * 255)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle the selection of an option."""

        dynamic_widget_placeholder = self.query_one(
            "#dynamic-widget-placeholder", Horizontal
        )

        # Remove all children from the placeholder
        for child in list(dynamic_widget_placeholder.children):
            # dynamic_widget_placeholder.remove(child)
            child.remove()
        genre = event.option.prompt
        value = self.genre_values[genre]
        # Create a new Vertical container with a Button and Label
        data = distribution_of_feature(f"genre_{genre}")
        sparky = Sparkline(data=data, summary_function=max, id="feature-distribution")

        dynamic_root_vertical = Vertical()
        dynamic_vertical = Horizontal()
        dynamic_widget_placeholder.mount(dynamic_root_vertical)
        dynamic_root_vertical.mount(dynamic_vertical)

        dynamic_root_vertical.mount(sparky)

        new_slider = MySlider(min=0, max=99, value=value * 100, id=f"{genre}-amp")
        new_label = Label(id=f"{genre}-amp-label")
        new_slider.styles.background = Color(value * 255, value * 255, value * 255)
        new_label.styles.margin = (0, 0)
        new_label.styles.content_align = ("left", "top")
        dynamic_vertical.mount(new_slider)
        dynamic_vertical.mount(new_label)
        self.selected_genre = genre
        self.selected_value = value


def distribution_of_feature(feature):

    database_path = "database/paula.sqlite"
    connection = sqlite3.connect(database_path)
    cursor = connection.cursor()
    sql = "SELECT count FROM feature_distribution WHERE feature_name = ?;"
    cursor.execute(
        sql,
        (feature,),
    )
    results = cursor.fetchall()
    connection.close()
    return [tup[0] for tup in results]


class SpinalTapApp(App):
    def compose(self) -> ComposeResult:
        yield GenreSliders()


if __name__ == "__main__":
    app = SpinalTapApp()
    app.run()
