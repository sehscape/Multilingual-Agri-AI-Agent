"""Application entry point – imports and launches the Gradio UI."""
import os

from app.ui.gradio_app import build_ui
from app.utils.logging import get_logger, enable_utf8_console

enable_utf8_console()
logger = get_logger(__name__)

# A real hosting platform (Hugging Face Spaces, Render, Railway, …) provides the
# public URL and sets PORT, so the temporary gradio.live share tunnel is only
# wanted for quick local demos.
_ON_HOST = bool(os.getenv("SPACE_ID") or os.getenv("RENDER") or os.getenv("PORT"))
_PORT = int(os.getenv("PORT", "7860"))


def main() -> None:
    logger.info("Starting Multilingual Agri Assistant (port=%s, hosted=%s)", _PORT, _ON_HOST)
    from app.ui.gradio_app import _CSS
    import gradio as gr
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=_PORT,
        share=not _ON_HOST,
        theme=gr.themes.Soft(),
        css=_CSS,
    )


if __name__ == "__main__":
    main()
