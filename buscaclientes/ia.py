"""Análisis opcional con Claude: lee la ficha y las reseñas de cada lead y devuelve
si es cliente ideal, el segmento, un ajuste de puntaje y UNA frase de apertura personal.

Los mensajes siguen saliendo de las plantillas del perfil: la IA solo escribe el gancho,
así el tono y la oferta quedan bajo control del negocio.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from pydantic import BaseModel, Field

COSTO_POR_LEAD = {  # USD aprox. por lead con 15 reseñas (entrada ~5k tokens, salida ~400)
    "claude-opus-5-5": 0.03,
    "claude-sonnet-5-5": 0.015,
    "claude-haiku-5-5": 0.001,
}


class Analisis(BaseModel):
    es_cliente_ideal: bool = Field(description="False si no es del rubro o no le sirve lo que vendemos")
    segmento: str = Field(description="Uno de los ids de segmento dados, o 'general'")
    ajuste_puntaje: int = Field(description="Entre -30 y 20 según qué tan buen cliente parece")
    motivo: str = Field(description="Una línea: por qué ese puntaje")
    gancho: str = Field(description="Una sola frase de apertura personal, sin punto final, máx. 25 palabras")
    citas: list[str] = Field(description="Hasta 2 frases cortas de reseñas que justifican el segmento, casi textuales")


def activa(perfil: dict) -> bool:
    usar = str(perfil["ia"]["usar"]).lower()
    if usar in ("no", "false", "0"):
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def costo_estimado(perfil: dict, cantidad: int) -> float:
    return COSTO_POR_LEAD.get(perfil["ia"]["modelo"], 0.03) * cantidad


def _sistema(perfil: dict) -> str:
    neg = perfil["negocio"]
    segs = "\n".join(f"- {s['id']}: palabras típicas {', '.join(s['palabras'][:8])}" for s in perfil["segmentos"])
    return f"""Trabajás en el equipo comercial de {neg['nombre']}.
Qué vendemos: {neg['presentacion']}
Cliente ideal: {perfil['ia']['cliente_ideal'] or 'negocios del rubro buscado que puedan comprarnos o recomendarnos'}

Vas a recibir la ficha de Google Maps (o de una lista) de un posible cliente y sus reseñas.
1. Decidí si es cliente ideal. Si no es del rubro, es una franquicia o cadena que no decide local, o no le sirve lo que vendemos, poné false.
2. Elegí el segmento que mejor lo describe entre estos ids (o 'general'):
{segs}
3. Ajustá el puntaje entre -30 y 20.
4. Escribí UNA frase de apertura para el primer mensaje, que muestre que miramos su negocio: algo específico y verdadero
   de la ficha o las reseñas (qué hace, en qué se destaca). Tono: {perfil['ia']['tono']}.
   Trato de usted. Sin signos de apertura ¡ ni ¿. Sin punto final. Sin halagos vacíos, sin frases de folleto,
   sin citar quejas ni nombres de pacientes o clientes. Si no hay nada específico, escribí algo simple sobre su rubro.
   Tiene que poder seguir con "y le escribo por ...". Ejemplo: "Vi que hace muchas lipotransferencias en su consultorio de Palermo"
5. Citá hasta 2 frases cortas reales de las reseñas que justifiquen el segmento. No inventes."""


def archivo_cache(perfil: dict, lead: dict, cache: Path) -> Path:
    clave = hashlib.sha1(f"{lead['id']}|{perfil['ia']['modelo']}|{perfil['negocio']['presentacion']}".encode()).hexdigest()[:20]
    return cache / f"ia_{clave}.json"


def analizar(cliente, perfil: dict, lead: dict, cache: Path) -> dict | None:
    cache.mkdir(parents=True, exist_ok=True)
    archivo = archivo_cache(perfil, lead, cache)
    if archivo.exists():
        return json.loads(archivo.read_text())

    import anthropic

    ficha = {k: lead.get(k) for k in ("nombre", "categoria", "categorias", "direccion", "web", "rating", "cant_resenas", "instagram", "notas")}
    resenas = "\n".join(f"- [{r['estrellas']}★] {r['texto'][:600]}" for r in lead.get("resenas", [])[:20]) or "(sin reseñas)"
    contenido = f"FICHA:\n{json.dumps(ficha, ensure_ascii=False)}\n\nRESEÑAS:\n{resenas}"
    ids = {s["id"] for s in perfil["segmentos"]} | {"general"}

    for intento in range(3):
        try:
            resp = cliente.beta.messages.parse(
                model=perfil["ia"]["modelo"],
                max_tokens=2000,
                system=_sistema(perfil),
                output_config={"effort": "low"},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{"role": "user", "content": contenido}],
                output_format=Analisis,
            )
            break
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError):
            time.sleep(5 * (intento + 1))
    else:
        return None
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        return None
    a = resp.parsed_output.model_dump()
    a["segmento"] = a["segmento"] if a["segmento"] in ids else "general"
    a["ajuste_puntaje"] = max(-30, min(20, a["ajuste_puntaje"]))
    a["gancho"] = a["gancho"].replace("¡", "").replace("¿", "").rstrip(" .")
    archivo.write_text(json.dumps(a, ensure_ascii=False))
    return a


def cliente_nuevo():
    import anthropic

    # base_url explícito: algunos entornos (Claude Code) tienen ANTHROPIC_BASE_URL apuntando a un proxy
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], base_url=os.environ.get("BC_ANTHROPIC_BASE_URL", "https://api.anthropic.com"))
