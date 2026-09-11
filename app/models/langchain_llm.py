"""LangChain LLM adapter.

Wraps any of the project's `BaseLLM` backends (StubLLM, HuggingFaceLocalLLM,
HuggingFaceInferenceAPILLM) as a LangChain `LLM`, so the model layer stays
unchanged and LangChain only sees a text-in / text-out callable.
"""
from __future__ import annotations

from typing import Any, List, Optional

from langchain_core.language_models.llms import LLM
from pydantic import ConfigDict

from app.models.llm import BaseLLM


class LangChainLLMAdapter(LLM):
    """Expose a project BaseLLM to LangChain."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    inner: BaseLLM

    @property
    def _llm_type(self) -> str:
        return "agri-agent-wrapped-llm"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> str:
        text = self.inner.generate(prompt)
        # Honour stop sequences — the ReAct agent passes "\nObservation" so the
        # model never invents a tool result itself.
        for s in stop or []:
            idx = text.find(s)
            if idx != -1:
                text = text[:idx]
        return text
