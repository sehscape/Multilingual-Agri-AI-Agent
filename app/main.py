"""Application entry point – imports and launches the Gradio UI."""
from app.ui.gradio_app import build_ui
from app.utils.logging import get_logger

logger = get_logger(__name__)


def main() -> None:
    logger.info("Starting Multilingual Agri Assistant")
    demo = build_ui()
    import gradio as gr
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, theme=gr.themes.Soft())


if __name__ == "__main__":
    main()
