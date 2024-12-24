from textual import on
from textual.app import App, ComposeResult
from textual.containers import Center, Vertical, Horizontal
from textual.widgets import Label, OptionList
from textual.color import Color
from textual_slider import Slider
from textual.widgets.option_list import Option, Separator
from textual.widget import Widget


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
        self.styles.height = "16"
        self.styles.width = "40"
        self.selected_genre = None
        self.selected_genre_value = -1.0

    def on_click(self, event) -> None:
        # Handle the click event
        pass

    def compose(self) -> ComposeResult:
        genre_array = list(self.genre_values.keys())
        options = []
        for index, option in enumerate(genre_array):
            options.append(Option(f"{option}", id=f"id-{option}"))
        option_list = OptionList(*options)
        yield option_list
        yield Horizontal(id="dynamic-widget-placeholder")

    @on(Slider.Changed)
    def on_slider_changed(self, event: Slider.Changed) -> None:
        """Handle changes for any slider."""
        # Determine the slider ID
        slider_id = event.slider.id

        # Construct the corresponding label ID
        label_id = f"{slider_id}-label"
        # Find the label widget and update it
        label = self.query_one(f"#{label_id}", Label)
        genre = str(label_id).replace("-amp-label", "")
        self.selected_genre = genre

        value = event.value / 100
        self.genre_values[genre] = value
        self.selected_genre = value

        label.update(f"{event.value/100}\n-\n{(event.value+1)/100}")
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
        dynamic_vertical = Horizontal()
        dynamic_widget_placeholder.mount(dynamic_vertical)

        new_slider = Slider(min=0, max=99, value=value * 99, id=f"{genre}-amp")
        new_label = Label(id=f"{genre}-amp-label")
        new_slider.styles.background = Color(value * 255, value * 255, value * 255)
        new_label.styles.margin = (0, 0)
        new_label.styles.content_align = ("left", "top")
        dynamic_vertical.mount(new_slider)
        dynamic_vertical.mount(new_label)
        self.selected_genre = genre
        self.selected_genre = value


class SpinalTapApp(App):
    def compose(self) -> ComposeResult:
        yield GenreSliders()


if __name__ == "__main__":
    app = SpinalTapApp()
    app.run()
