from PIL import Image
from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.css.scalar import Scalar
from textual.events import Click, MouseDown, MouseUp
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static
from textual_image.widget import HalfcellImage, SixelImage, TGPImage, UnicodeImage
from textual_image.widget import Image as AutoImage

RENDERING_METHODS = {
    "auto": AutoImage,
    "tgp": TGPImage,
    "sixel": SixelImage,
    "halfcell": HalfcellImage,
    "unicode": UnicodeImage,
}


class CustomButton(Widget):

    class ButtonClicked(Message):
        """Custom message indicating the button was clicked."""

        def __init__(self, sender: "CustomButton", button_id: str):
            super().__init__()
            self.sender = sender
            self.button_id = button_id

    def __init__(self, path: str, id: str = None):
        super().__init__(id=id)
        self.button_id = id
        self.image_icon_path = path
        image_normal = self.overlay_image(self.image_icon_path)
        image_pushed = self.overlay_image(self.image_icon_path, True)

        Image = RENDERING_METHODS["auto"]
        self.image_widget_normal = Image(image_normal, id="image_widget_normal")
        self.image_widget_pushed = Image(image_pushed, id="image_widget_pushed")

        self.styles.width = Scalar.parse("7")
        self.styles.height = Scalar.parse("3")
        self.image_widget_normal.styles.width = Scalar.parse("7")
        self.image_widget_normal.styles.height = Scalar.parse("3")
        self.image_widget_normal.styles.padding = 0
        self.image_widget_normal.styles.margin = 0

        self.image_widget_pushed.styles.width = Scalar.parse("7")
        self.image_widget_pushed.styles.height = Scalar.parse("3")
        self.image_widget_pushed.styles.padding = 0
        self.image_widget_pushed.styles.margin = 0

    def overlay_image(self, icon_path, is_pushed=False):
        button_size = (255, 255)  # Width, Height
        icon_size = (180, 180)  # Width, Height
        if not is_pushed:
            background_path = (
                "c:/Users/susan/paula/application/gui/images/button_normal.png"
            )
        else:
            background_path = (
                "c:/Users/susan/paula/application/gui/images/button_pushed.png"
            )
        background = Image.open(background_path).convert("RGBA").resize(button_size)

        overlay = Image.open(icon_path).convert("RGBA").resize(icon_size)
        canvas = Image.new(
            "RGBA", button_size, (255, 255, 255, 0)
        )  # (R, G, B, A) where A=0 for transparency
        x_offset = (button_size[0] - overlay.width) // 2
        y_offset = (button_size[1] - overlay.height) // 2
        canvas.paste(overlay, (x_offset, y_offset), mask=overlay)

        alpha = 255
        overlay = Image.blend(
            Image.new("RGBA", canvas.size, (255, 255, 255, 0)), canvas, alpha / 255
        )

        # Composite the images
        return Image.alpha_composite(background, overlay)

    def on_mount(self, event):
        if isinstance(event, MouseDown) and event.button == 1:
            for child in list(self.children):
                child.remove()
            self.mount(self.image_widget_pushed)
        if isinstance(event, MouseUp) and event.button == 1:
            for child in list(self.children):
                child.remove()
            self.mount(self.image_widget_normal)
        else:
            self.mount(self.image_widget_normal)

    def on_mouse_down(self, event: MouseDown):
        self.on_mount(event)

    def on_mouse_up(self, event: MouseUp):
        self.on_mount(event)
        self.post_message(self.ButtonClicked(self, button_id=self.button_id))


class MyApp(App):

    def compose(self) -> ComposeResult:
        """Compose the app's layout."""
        with Horizontal():
            yield CustomButton(
                path="c:/Users/susan/paula/application/gui/images/music-play.png",
                id="play",
            )
            yield CustomButton(
                path="c:/Users/susan/paula/application/gui/images/music-stop.png",
                id="stop",
            )
            yield CustomButton(
                path="c:/Users/susan/paula/application/gui/images/backwards.png",
                id="backward",
            )
            yield CustomButton(
                path="c:/Users/susan/paula/application/gui/images/forwards.png",
                id="forward",
            )

    async def on_custom_button_button_clicked(
        self, message: CustomButton.ButtonClicked
    ) -> None:
        # Simulate a click on the button
        button = self.query_one(f"#{message.button_id}", CustomButton)
        if button:
            print("hfhf")


if __name__ == "__main__":
    MyApp().run()
