"""Application entry point.

By default this serves the web app and its JSON API (app/web/server.py), with
the original Gradio screen mounted at /classic. Set UI=classic to run the
Gradio screen on its own instead (it can then open a temporary public link).
"""
import os
import threading

from app.ui.gradio_app import build_ui, build_theme, warm_up, _CSS, _HEAD
from app.utils.logging import get_logger, enable_utf8_console

enable_utf8_console()
logger = get_logger(__name__)

# A real hosting platform (Hugging Face Spaces, Render, Railway, …) provides the
# public URL and sets PORT, so the temporary gradio.live share tunnel is only
# wanted for quick local demos.
_ON_HOST = bool(os.getenv("SPACE_ID") or os.getenv("RENDER") or os.getenv("PORT"))
_PORT = int(os.getenv("PORT", "7860"))
_UI = os.getenv("UI", "web").lower()


def main() -> None:
    logger.info("Starting Multilingual Agri Assistant (ui=%s, port=%s, hosted=%s)",
                _UI, _PORT, _ON_HOST)
    # Load the speech model and the scheme index while the page is coming up.
    threading.Thread(target=warm_up, name="warm-up", daemon=True).start()

    if _UI == "classic":
        demo = build_ui()
        # Gradio 6 takes theme/css at launch() rather than on Blocks().
        demo.launch(
            server_name="0.0.0.0",
            server_port=_PORT,
            share=not _ON_HOST,
            theme=build_theme(),
            css=_CSS,
            head=_HEAD,
        )
        return

    import uvicorn
    from app.web.server import create_app
    logger.info("Web app on http://127.0.0.1:%s  (classic screen: /classic, API docs: /api/docs)",
                _PORT)
    uvicorn.run(create_app(), host="0.0.0.0", port=_PORT, log_level="warning",
                proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
