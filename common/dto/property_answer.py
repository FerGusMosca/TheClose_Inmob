# common/dto/property_answer.py
import logging, os
from pathlib import Path

from common.llm_client.base_llm import BaseLLM
from common.util.builder.llm_factory import LLMFactory
from common.util.search.property_searcher import SearchContext

log = logging.getLogger(__name__)


class PropertyAnswer:

    def __init__(self, openai_api_key, prompt_path,
                 llm_class="common.llm_client.openai_llm.OpenAILLM",
                 llm_model="gpt-4o-mini", llm_temperature=0.0):
        os.environ["OPENAI_API_KEY"] = openai_api_key
        self._llm: BaseLLM = LLMFactory.from_class_path(
            class_path=llm_class, model_name=llm_model, temperature=llm_temperature)
        self._prompt_template = Path(prompt_path).read_text(encoding="utf-8") \
            if Path(prompt_path).exists() else self._default_prompt()

    def get_answer(self, context: SearchContext) -> str:
        """Returns complete LLM answer as a single string."""
        if not context.properties:
            return "No encontré propiedades que coincidan con tu búsqueda. Probá con otros criterios."
        prompt = (self._prompt_template
                  .replace("{query}",      context.query)
                  .replace("{properties}", self._format_properties(context.properties))
                  .replace("{count}",      str(len(context.properties))))
        log.info("PropertyAnswer.get_answer | props=%d", len(context.properties))
        return self._llm.invoke(prompt)

    @staticmethod
    def _format_properties(properties) -> str:
        lines = []
        for i, p in enumerate(properties, 1):
            price_str = f"{p.currency} {p.price:,.0f}" if p.price else "Sin precio"
            attrs = []
            if p.ambientes:   attrs.append(f"{p.ambientes} amb.")
            if p.dormitorios: attrs.append(f"{p.dormitorios} dorm.")
            if p.banos:       attrs.append(f"{p.banos} baños")
            if p.m2_total:    attrs.append(f"{p.m2_total:.0f} m²")
            line = f"{i}. {p.neighborhood or ''}"
            if p.address:  line += f" — {p.address}"
            line += f" | Precio: {price_str}"
            if p.expensas: line += f" | Exp: ARS {p.expensas:,.0f}"
            if attrs:      line += f" | {' · '.join(attrs)}"
            lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _default_prompt() -> str:
        return ("Sos experto inmobiliario de Buenos Aires.\n"
                "El usuario preguntó: {query}\n\n"
                "Propiedades encontradas:\n{properties}\n\n"
                "Respondé en español, conciso y útil.")