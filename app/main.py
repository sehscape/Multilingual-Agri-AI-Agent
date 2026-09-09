"""Application entry point – imports and launches the Gradio UI."""
import os

from app.ui.gradio_app import build_ui
from app.utils.logging import get_logger, enable_utf8_console

enable_utf8_console()
logger = get_logger(__name__)

# On Hugging Face Spaces the platform provides the public URL, so a share tunnel
# is unnecessary (and unsupported). On a self-hosted server (e.g. Oracle Cloud)
# with a real public IP, GRADIO_SHARE=false does the same. Locally, the default
# (share=True) gives a temporary public link for quick demos.
_ON_SPACES = bool(os.getenv("SPACE_ID"))
_SHARE_OVERRIDE = os.getenv("GRADIO_SHARE")  # "true" / "false", optional


def main() -> None:
    logger.info("Starting Multilingual Agri Assistant")
    from app.ui.gradio_app import _CSS
    import gradio as gr
    demo = build_ui()
    if _SHARE_OVERRIDE is not None:
        use_share = _SHARE_OVERRIDE.strip().lower() == "true"
    else:
        use_share = not _ON_SPACES
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=use_share,
        theme=gr.themes.Soft(),
        css=_CSS,
    )


if __name__ == "__main__":
    main()
