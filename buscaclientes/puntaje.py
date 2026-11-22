"""Segmento, puntaje 0-100, localidad y modalidad (visita o remoto) de cada lead.

Sin IA: cuenta palabras clave del perfil en nombre, categoría, web, notas y reseñas.
"""

from __future__ import annotations

import math
import re
import unicodedata

_CP = re.compile(r"^[A-Z]?\d{4,8}(-\d{3})?\s*[A-Z]{0,3}\s+(?=\D)")  # C1426 EOQ, B7600, 7500000 (CL), 06600 (MX), 01310-100 (BR)
_PAISES = {"argentina", "chile", "uruguay", "paraguay", "peru", "mexico", "colombia", "espana", "bolivia", "ecuador",
           "venezuela", "costarica", "panama", "guatemala", "republicadominicana", "estadosunidos", "usa", "brasil"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def _rx(palabras: list[str]) -> re.Pattern | None:
    """Cada palabra tiene que empezar palabra: 'bar' encuentra 'bar' y 'bares', no 'barrio'... salvo que
    se escriba completa en el perfil. Para evitar prefijos ambiguos, usá la palabra entera o 'bar\\b'."""
    ps = [p for p in palabras if p]
    return re.compile("|".join(f"(?<!\\w)(?:{p})" for p in ps), re.I) if ps else None


def texto_lead(l: dict) -> str:
    return " ".join(
        [l.get("nombre", ""), l.get("categoria", ""), " ".join(l.get("categorias", [])), l.get("web", ""), l.get("notas", "")]
        + [r["texto"] for r in l.get("resenas", [])]
    )


def localidad(l: dict) -> str:
    """'Calle 123, B7600 Mar del Plata, Provincia de Buenos Aires, Argentina' -> 'Mar del Plata, Provincia de Buenos Aires'."""
    if not l.get("direccion"):  # leads de una lista propia: la ciudad que vino en el CSV
        return l.get("ciudad", "")
    partes = [p.strip() for p in (l.get("direccion") or "").split(",") if p.strip()]
    if len(partes) > 1 and norm(partes[-1]) in _PAISES:
        partes = partes[:-1]
    loc = ""
    if len(partes) >= 2:
        loc = _CP.sub("", partes[-1]).strip()
        if loc.lower().startswith(("provincia de", "región", "region", "estado de", "departamento")) or len(loc) < 3:
            previo = _CP.sub("", partes[-2]).strip()
            if len(previo) >= 3 and not re.search(r"\d", previo):
                loc = f"{previo}, {loc}" if len(loc) >= 3 else previo
    ciudad = l.get("ciudad") or ""
    if not loc or (len(ciudad) > 3 and ciudad.lower() not in loc.lower()):
        loc = ", ".join(x for x in (loc, ciudad) if x and len(x) > 3)
    return loc


def es_del_rubro(l: dict, perfil: dict) -> bool:
    cat = " ".join([l.get("categoria", ""), " ".join(l.get("categorias", [])), l.get("nombre", "")])
    si, no = _rx(perfil["filtro"]["categorias_si"]), _rx(perfil["filtro"]["categorias_no"])
    if no and no.search(l.get("categoria", "")):
        return False
    if si and l.get("origen") == "Google Maps" and not si.search(cat):
        return False
    return True


def segmento(l: dict, perfil: dict) -> tuple[dict, dict[str, int]]:
    """Devuelve (segmento elegido, conteo de palabras por segmento)."""
    txt = texto_lead(l)
    conteo = {}
    for s in perfil["segmentos"]:
        rx = _rx(s["palabras"])
        conteo[s["id"]] = len(rx.findall(txt)) if rx else 0
    forzado = l.get("segmento_forzado")
    for s in perfil["segmentos"]:
        if forzado and s["id"] == forzado:
            return s, conteo
    # el orden del perfil es la prioridad: gana el primero que llega a su mínimo
    for s in perfil["segmentos"]:
        if conteo[s["id"]] >= s["minimo"]:
            return s, conteo
    return perfil["segmento_general"], conteo


def puntuar(l: dict, perfil: dict, conteo: dict[str, int]) -> tuple[int, str]:
    if not es_del_rubro(l, perfil):
        return 5, "no parece del rubro buscado"
    p = 30
    motivo = []
    suma = 0
    for s in perfil["segmentos"]:
        c = conteo.get(s["id"], 0)
        if c:
            suma += c * s["peso"]
            motivo.append(f"{s['id']} x{c}")
    p += min(40, suma)
    volumen = l.get("cant_resenas") or l.get("volumen") or 0
    if volumen:
        p += min(18, int(math.log10(volumen + 1) * 7))
        motivo.append(f"{volumen} {'reseñas' if l.get('cant_resenas') else 'seguidores/300'}")
    if (l.get("rating") or 0) >= 4.6 and (l.get("cant_resenas") or 0) >= 20:
        p += 3
    if l.get("emails"):
        p += 4
    if l.get("telefono"):
        p += 2
    txt = texto_lead(l)
    for pen in perfil["penalizaciones"]:
        rx = _rx(pen.get("palabras", []))
        if rx and len(rx.findall(txt)) >= pen.get("minimo", 1):
            p -= pen.get("puntos", 15)
            motivo.append(pen.get("motivo", "penalizado"))
    return max(0, min(100, p)), ", ".join(motivo) or "sin señales del rubro"


def visitable(loc: str, perfil: dict) -> bool:
    rx = _rx(perfil["ofrecimiento"]["zonas_visita"])
    return bool(rx and rx.search(loc or ""))
