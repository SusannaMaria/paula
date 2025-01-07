from time import sleep

from PIL import Image
from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.css.scalar import Scalar
from textual.events import Click, Event, MouseDown, MouseUp
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
MODES = {"play": "", "pause": "", "resume": ""}


class CustomButton(Widget):

    class ButtonClicked(Message):
        """Custom message indicating the button was clicked."""

        def __init__(self, sender: "CustomButton", button_id: str):
            super().__init__()
            self.sender = sender
            self.button_id = button_id

    def __init__(self, id: str, path: str = None, modes=None):
        super().__init__(id=id)
        self.styles.width = Scalar.parse("7")
        self.styles.height = Scalar.parse("3")
        self.button_id = id

        if modes:
            self.modes = modes
        else:
            self.modes = [{"id": f"{id}", "path": f"{path}"}]

        self.mode_idx = 0

        for mode in self.modes:
            image_normal = self.overlay_image(mode["path"])
            image_pushed = self.overlay_image(mode["path"], True)
            image_disabled = self.overlay_image(mode["path"], False, True)
            mode["image_pushed"] = image_pushed
            mode["image_normal"] = image_normal
            mode["image_disabled"] = image_disabled

        mode = self.modes[self.mode_idx]
        Image = RENDERING_METHODS["auto"]
        self.image = Image(mode["image_normal"], id=mode["id"])
        self.image.styles.width = Scalar.parse("7")
        self.image.styles.height = Scalar.parse("3")
        self.image.styles.padding = 0
        self.image.styles.margin = 0
        self.block_mouse_event = False

    def set_mode_idx(self, id):
        for index, mode in enumerate(self.modes):
            if id in mode["id"]:
                self.mode_idx = index
                self.image.image = mode["image_normal"]
                return True
        return False

    def get_mode(self):
        return self.modes[self.mode_idx]["id"]

    def overlay_image(self, icon_path, is_pushed=False, is_disabled=False):
        button_size = (255, 255)  # Width, Height
        icon_size = (180, 180)  # Width, Height
        if not is_pushed:
            background_path = (
                "c:/Users/susan/paula/application/gui/images/button_dark_normal.png"
            )
        else:
            background_path = (
                "c:/Users/susan/paula/application/gui/images/button_dark_pushed.png"
            )
        background = Image.open(background_path).convert("RGBA").resize(button_size)

        overlay = Image.open(icon_path).convert("RGBA").resize(icon_size)
        canvas = Image.new(
            "RGBA", button_size, (255, 255, 255, 0)
        )  # (R, G, B, A) where A=0 for transparency
        x_offset = (button_size[0] - overlay.width) // 2
        y_offset = (button_size[1] - overlay.height) // 2
        canvas.paste(overlay, (x_offset, y_offset), mask=overlay)
        if is_disabled:
            alpha = 10
        else:
            alpha = 140
        overlay = Image.blend(
            Image.new("RGBA", canvas.size, (255, 255, 255, 0)), canvas, alpha / 255
        )

        # Composite the images
        return Image.alpha_composite(background, overlay)

    def on_mount(self, event):
        # for child in list(self.children):
        #     child.remove()
        self.mount(self.image)

    def on_mouse_down(self, event: MouseDown):
        if not self.block_mouse_event:
            self.set_state("pushed")

    def on_mouse_up(self, event: MouseUp):
        if not self.block_mouse_event:
            self.set_state("normal")

    def set_state(self, state="normal"):
        self.block_mouse_event = True
        mode = self.modes[self.mode_idx]
        if "normal" in state:
            # self.image.image = mode["image_normal"]
            self.post_message(self.ButtonClicked(self, button_id=self.button_id))
        elif "pushed" in state:
            pass
            # self.image.image = mode["image_pushed"]
        elif "disabled" in state:
            # self.image.image = mode["image_disabled"]
            pass
        self.block_mouse_event = False


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
