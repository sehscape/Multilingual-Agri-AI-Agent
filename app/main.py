"""Application entry point – imports and launches the Gradio UI."""
import os

from app.ui.gradio_app import build_ui
from app.utils.logging import get_logger, enable_utf8_console

enable_utf8_console()
logger = get_logger(__name__)

# On Hugging Face Spaces the platform provides the public URL, so a share tunnel
# is unnecessary (and unsupported). Locally, share=True gives a public link.
_ON_SPACES = bool(os.getenv("SPACE_ID"))


def main() -> None:
    logger.info("Starting Multilingual Agri Assistant")
    from app.ui.gradio_app import _CSS
    import gradio as gr
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=not _ON_SPACES,
        theme=gr.themes.Soft(),
        css=_CSS,
    )


if __name__ == "__main__":
    main()
