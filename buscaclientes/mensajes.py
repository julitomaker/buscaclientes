"""Arma la secuencia de mensajes de cada lead a partir de las plantillas del perfil."""

from __future__ import annotations

import re

_TITULO = re.compile(
    r"\b(Dra|Dr|Lic|Ing|Arq|Odont|Cdor|Cdora|Esc)\.?\s+((?:[A-ZÁÉÍÓÚÑ]\.?\s*)*[A-ZÁÉÍÓÚÑ][\wáéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñü]+){0,3})"
)
_FEMENINO = ("Dra", "Cdora")


class _Seguro(dict):
    def __missing__(self, k):  # una variable que no existe queda visible para corregirla
        return "{" + k + "}"


def titulo_apellido(nombre: str) -> str:
    """'Cirugía Plástica Dr. Juan Carlos Elías' -> 'Dr. Elías'."""
    m = _TITULO.search(nombre or "")
    if not m:
        return ""
    partes = [p for p in m.group(2).split() if len(p.strip(".")) > 1]
    if not partes:
        return ""
    return f"{m.group(1)}. {partes[-1]}"


def nombre_corto(nombre: str) -> str:
    n = re.split(r"\s[|·–—-]\s|\s\|", nombre or "")[0].strip()
    return n[:40]


def variables(l: dict, seg: dict, perfil: dict, visita: bool, gancho: str = "") -> dict:
    neg, of = perfil["negocio"], perfil["ofrecimiento"]
    modo = of["visita"] if visita else of["remoto"]
    t = titulo_apellido(l.get("nombre", "")) if perfil["personas"]["titulos"] else ""
    tiene_email = bool(l.get("emails"))
    if t:
        al = ("a la " if t.startswith(_FEMENINO) else "al ") + t
    else:
        al = f"al equipo de {nombre_corto(l.get('nombre', ''))}"
    muestra = seg.get("muestra_detalle") or perfil["segmento_general"].get("muestra_detalle") or ""
    v = {
        "negocio": neg["nombre"],
        "remitente": neg["remitente"],
        "firma": neg["firma"],
        "presentacion": neg["presentacion"],
        "presentacion_corta": neg["presentacion_corta"],
        "motivo": neg["motivo"],
        "prueba_social": neg["prueba_social"],
        "beneficio_extra": (", y " + neg["beneficio_extra"]) if neg["beneficio_extra"] else "",
        "gancho": gancho or seg.get("gancho") or perfil["segmento_general"]["gancho"],
        "asunto": seg.get("asunto") or perfil["segmento_general"].get("asunto") or f"{neg['nombre']}",
        "muestra": muestra,
        "trato_nombre": t,
        "trato_o_hola": t or "Hola",
        "saludo": f"{t}, buen día." if t else "Hola, buen día.",
        "saludo_dm": f"Hola {t}, como está?" if t else "Hola, como están?",
        "al_contacto": al,
        "lead": nombre_corto(l.get("nombre", "")),
        "ciudad": l.get("_localidad", ""),
        "canales": "mail e Instagram" if tiene_email and l.get("instagram") else ("mail" if tiene_email else "Instagram"),
        "evaluar": of["evaluar"],
    }
    for k in ("cta", "cta_dm", "oferta", "pedido", "cierre_verbo"):
        v[k] = modo[k].format_map(_Seguro(v))
    return v


def secuencia(l: dict, seg: dict, perfil: dict, visita: bool, gancho: str = "") -> dict[str, str]:
    v = variables(l, seg, perfil, visita, gancho)
    m = perfil["mensajes"]
    tiene_email = bool(l.get("emails"))
    def r(k: str) -> str:
        texto = m[k].format_map(_Seguro(v)).strip()
        # mayúscula al empezar oración (las variables suelen venir en minúscula)
        return re.sub(r"(^|[.!?]\s+|\n)([a-záéíóúñ])", lambda x: x.group(1) + x.group(2).upper(), texto)
    return {
        "asunto": v["asunto"] if tiene_email else "",
        "email1": r("email1") if tiene_email else "",
        "seguimiento": r("seguimiento") if tiene_email else "",
        "dm": r("dm") if tiene_email else r("dm_primero"),
        "llamada": r("llamada"),
        "cierre": r("cierre") if tiene_email else "",
        "modalidad": ("Visita" if visita else "Remoto") + ("" if tiene_email else " · arranca por DM"),
    }
