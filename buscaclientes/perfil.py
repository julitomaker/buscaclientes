"""Perfil de un negocio: qué vende, a quién busca, cómo puntúa y qué mensajes manda.

Todo lo específico de un rubro vive en proyectos/<nombre>/perfil.yaml. Lo que no se completa
toma los valores de DEFAULTS.
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

DEFAULTS: dict = {
    "negocio": {
        "nombre": "",
        "remitente": "",
        "firma": "",
        "presentacion": "",          # una línea: qué vendés y por qué conviene
        "presentacion_corta": "",    # versión de media línea para el DM
        "motivo": "",                # "las fajas que usan sus pacientes después"
        "prueba_social": "",         # dato real y comprobable, sin inflar
        "beneficio_extra": "",       # algo concreto para el cliente del cliente
    },
    "busqueda": {
        "terminos": [],
        "zonas": [],
        "por_busqueda": 12,
        "resenas": 15,
        "idioma": "es",
        "contactos": True,           # emails y redes de la web (cuesta un poco más en Apify)
    },
    "filtro": {
        "categorias_si": [],         # si hay, el lugar tiene que matchear alguna (categoría o nombre)
        "categorias_no": [],         # se descartan
        "excluir": [],               # clientes actuales o ya contactados: usuario de Instagram o parte del nombre
    },
    "segmentos": [],                 # ver perfiles/plantilla.yaml
    "segmento_general": {
        "id": "general",
        "gancho": "Vi su trabajo",
        "asunto": "",
        "muestra_detalle": "",
    },
    "penalizaciones": [],            # [{palabras: [...], puntos: 20, motivo: "..."}]
    "personas": {
        "titulos": True,             # detecta "Dr./Dra./Lic./Ing./Arq." en el nombre para saludar
    },
    "ofrecimiento": {
        "zonas_visita": [],          # si la localidad matchea, se ofrece visita; si no, modo remoto
        "visita": {
            "cta": "Le interesaría que pase 10 minutos a mostrárselo, sin compromiso?",
            "cta_dm": "Le parece si coordino con su equipo un día que le quede cómodo?",
            "oferta": "paso 10 minutos y se lo muestro",
            "pedido": "quería pasar 10 minutos a mostrárselo. Me dirían un día y horario que les quede cómodo?",
            "cierre_verbo": "paso cuando le quede bien",
        },
        "remoto": {
            "cta": "Le interesaría que le mande más información, sin compromiso?",
            "cta_dm": "Le mando más info por acá?",
            "oferta": "le mando más información",
            "pedido": "quería mandarle más información. A qué mail o número se la envío?",
            "cierre_verbo": "se la mando",
        },
        "evaluar": "verlo",
    },
    "mensajes": {
        "email1": (
            "{saludo}\n\n{gancho} y le escribo por {motivo}.\n\n"
            "Soy {remitente}, de {negocio}: {presentacion}.\n\n{cta}\n\n{firma}"
        ),
        "seguimiento": (
            "{trato_o_hola}, le sumo un dato: {prueba_social}{beneficio_extra}.\n\n"
            "Si le sirve, {oferta}.\n\n{remitente}"
        ),
        "dm": (
            "{saludo_dm} Soy {remitente} de {negocio}, le escribí por mail la semana pasada.\n"
            "{presentacion_corta}.\n{cta_dm}"
        ),
        "dm_primero": (
            "{saludo_dm} Soy {remitente} de {negocio}, {presentacion_corta}.\n"
            "{gancho} y le escribo por {motivo}.\n{cta}"
        ),
        "llamada": (
            "Hola, buen día! Soy {remitente} de {negocio}. "
            "Le escribí {al_contacto} por {canales}: {pedido}"
        ),
        "cierre": (
            "{trato_o_hola}, no le lleno más la casilla. Si en algún momento quiere {evaluar}, "
            "me escribe y {cierre_verbo}. Y si prefiere que lo deje acá, también está perfecto.\n\n{remitente}"
        ),
    },
    "ia": {
        "usar": "auto",              # auto (si hay ANTHROPIC_API_KEY), si, no
        "modelo": "claude-opus-5-5",
        "maximo": 60,                # leads analizados por corrida (los de mejor puntaje)
        "cliente_ideal": "",         # descripción para que la IA descarte lo que no sirve
        "tono": "cálido y profesional, tipo WhatsApp argentino, sin frases de folleto",
    },
    "planilla": {
        "prioridad_alta": 70,
        "prioridad_media": 50,
        "minimo": 10,                # no se listan leads por debajo de este puntaje
        "por_semana": 15,
    },
}


def _fusionar(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _fusionar(out[k], v)
        elif v is not None:
            out[k] = v
    return out


def cargar(ruta: Path) -> dict:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    p = _fusionar(DEFAULTS, datos)
    errores = []
    if not p["negocio"]["nombre"]:
        errores.append("negocio.nombre")
    if not p["busqueda"]["terminos"]:
        errores.append("busqueda.terminos")
    for s in p["segmentos"]:
        s.setdefault("minimo", 1)
        s.setdefault("peso", 6)
        s.setdefault("palabras", [])
        if "id" not in s:
            errores.append("segmentos[].id")
    if errores:
        raise SystemExit(f"Falta completar en {ruta}: {', '.join(errores)}")
    neg = p["negocio"]
    neg["remitente"] = neg["remitente"] or neg["nombre"]
    neg["firma"] = neg["firma"] or f"{neg['remitente']}\n{neg['nombre']}"
    neg["presentacion_corta"] = neg["presentacion_corta"] or neg["presentacion"]
    return p
