"""Google Maps vía el actor oficial de Apify (compass/crawler-google-places).

Cada búsqueda (término + zona + parámetros) queda en caché: repetirla no vuelve a cobrar.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import requests

ACTOR = "compass~crawler-google-places"
COSTO_POR_LUGAR = 0.02  # USD aprox. con reseñas + contactos (medido: ~USD 2,75 por 158 lugares)


def _token() -> str:
    t = os.environ.get("APIFY_TOKEN", "")
    if not t:
        raise SystemExit("Falta APIFY_TOKEN en el archivo .env (console.apify.com → Settings → API & Integrations)")
    return t


def clave_cache(termino: str, zona: str, maximo: int, resenas: int, contactos: bool, idioma: str) -> str:
    base = f"{termino}|{zona}|{maximo}|{resenas}|{int(contactos)}|{idioma}"
    return hashlib.sha1(base.encode()).hexdigest()[:20]


def en_cache(cache: Path, clave: str) -> bool:
    return (cache / f"maps_{clave}.json").exists()


def buscar(termino: str, zona: str, maximo: int, resenas: int, contactos: bool, idioma: str, cache: Path) -> dict:
    """Devuelve {"termino", "zona", "items"} (de caché si ya se buscó)."""
    cache.mkdir(parents=True, exist_ok=True)
    clave = clave_cache(termino, zona, maximo, resenas, contactos, idioma)
    archivo = cache / f"maps_{clave}.json"
    if archivo.exists():
        return json.loads(archivo.read_text())
    cuerpo = {
        "searchStringsArray": [termino],
        "locationQuery": zona,
        "maxCrawledPlacesPerSearch": maximo,
        "language": idioma,
        "skipClosedPlaces": True,
        "maxReviews": resenas,
        "reviewsSort": "newest",
        "scrapeReviewsPersonalData": False,
        "scrapeContacts": contactos,
    }
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?timeout=600"
    r = requests.post(url, json=cuerpo, headers={"Authorization": f"Bearer {_token()}"}, timeout=660)
    if not r.ok:
        raise RuntimeError(f"Apify {r.status_code}: {r.text[:300]}")
    items = r.json()
    archivo.write_text(json.dumps({"termino": termino, "zona": zona, "items": items}, ensure_ascii=False))
    return {"termino": termino, "zona": zona, "items": items}


def credito() -> tuple[float, float]:
    r = requests.get("https://api.apify.com/v2/users/me/limits", headers={"Authorization": f"Bearer {_token()}"}, timeout=30)
    r.raise_for_status()
    d = r.json()["data"]
    return float(d["current"].get("monthlyUsageUsd") or 0), float(d["limits"].get("maxMonthlyUsageUsd") or 0)


def _lista(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x) for x in v if x]


def normalizar(item: dict, termino: str = "", zona: str = "") -> dict:
    resenas = []
    for rv in item.get("reviews") or []:
        txt = (rv.get("text") or rv.get("textTranslated") or "").replace("<br>", " ").strip()
        if txt:
            resenas.append({"estrellas": rv.get("stars"), "fecha": (rv.get("publishedAtDate") or "")[:10], "texto": txt[:1200]})
    igs = _lista(item.get("instagrams"))
    return {
        "id": item.get("placeId") or f"{item.get('title')}|{item.get('address')}",
        "origen": "Google Maps",
        "nombre": item.get("title") or "",
        "categoria": item.get("categoryName") or "",
        "categorias": _lista(item.get("categories")),
        "direccion": item.get("address") or "",
        "ciudad": item.get("city") or "",
        "telefono": item.get("phone") or item.get("phoneUnformatted") or "",
        "web": item.get("website") or "",
        "maps": item.get("url") or "",
        "rating": item.get("totalScore"),
        "cant_resenas": item.get("reviewsCount") or 0,
        "emails": _lista(item.get("emails")),
        "instagram": igs[0] if igs else "",
        "facebook": (_lista(item.get("facebooks")) or [""])[0],
        "linkedin": (_lista(item.get("linkedIns")) or [""])[0],
        "resenas": resenas,
        "notas": "",
        "busqueda": f"{termino} · {zona}".strip(" ·"),
    }
