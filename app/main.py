"""Application entry point – imports and launches the Gradio UI."""
from app.ui.gradio_app import build_ui
from app.utils.logging import get_logger

logger = get_logger(__name__)


def main() -> None:
    logger.info("Starting Multilingual Agri Assistant")
    from app.ui.gradio_app import _CSS
    import gradio as gr
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        theme=gr.themes.Soft(),
        css=_CSS,
    )


if __name__ == "__main__":
    main()
