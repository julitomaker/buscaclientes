"""clientes: buscá clientes en Google Maps, puntualos y armá la secuencia de mensajes.

  clientes nuevo <proyecto>                        crea proyectos/<proyecto>/perfil.yaml desde la plantilla
  clientes buscar <proyecto> [--zonas ...] [--si]  busca en Google Maps (pide confirmación del costo)
  clientes importar <proyecto> lista.csv           suma una lista propia (Instagram, ferias, contactos)
  clientes planilla <proyecto> [--sin-ia] [--si]   puntúa, arma mensajes y guarda Excel + CSV
  clientes estado <proyecto>                       cuántos leads hay y de dónde
  clientes credito                                 cuánto crédito de Apify queda este mes
  clientes demo                                    planilla de prueba con negocios ficticios (sin token, gratis)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import apify, ia, mensajes, perfil as perfil_mod, planilla, puntaje

RAIZ = Path(__file__).resolve().parent.parent
DATOS = Path(os.environ.get("BC_DATOS", RAIZ / "proyectos"))


# ---------- utilidades ----------
def cargar_env() -> None:
    for p in (Path.cwd() / ".env", RAIZ / ".env", DATOS / ".env"):
        if not p.exists():
            continue
        for linea in p.read_text().splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            k, v = linea.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if v:
                os.environ.setdefault(k.strip(), v)


def carpeta(nombre: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,40}", nombre):
        raise SystemExit("El nombre del proyecto va en minúsculas, sin espacios (ej: mi-negocio, agencia-norte)")
    return DATOS / nombre


def cargar_proyecto(nombre: str) -> tuple[Path, dict]:
    d = carpeta(nombre)
    ruta = d / "perfil.yaml"
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}. Crealo con: clientes nuevo {nombre}")
    return d, perfil_mod.cargar(ruta)


def leer_leads(d: Path) -> dict[str, dict]:
    f = d / "leads.json"
    return {l["id"]: l for l in json.loads(f.read_text())} if f.exists() else {}


def guardar_leads(d: Path, leads: dict[str, dict]) -> None:
    (d / "leads.json").write_text(json.dumps(list(leads.values()), ensure_ascii=False, indent=1))


def confirmar(texto: str, si: bool) -> bool:
    if si:
        return True
    if not sys.stdin.isatty():
        print(f"{texto} → agregá --si para confirmar")
        return False
    return input(f"{texto} Seguimos? [s/N] ").strip().lower() in ("s", "si", "sí", "y", "yes")


def handle_ig(ig: str) -> str:
    ig = re.sub(r"^https?://(www\.)?instagram\.com/", "", (ig or "").strip().rstrip("/"))
    return ig.split("?")[0].lstrip("@").lower()


# ---------- comandos ----------
def cmd_nuevo(a) -> None:
    d = carpeta(a.proyecto)
    destino = d / "perfil.yaml"
    if destino.exists():
        raise SystemExit(f"Ya existe {destino}")
    origen = RAIZ / "perfiles" / f"{a.desde}.yaml"
    if not origen.exists():
        opciones = ", ".join(p.stem for p in (RAIZ / "perfiles").glob("*.yaml"))
        raise SystemExit(f"No existe el perfil base «{a.desde}». Opciones: {opciones}")
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(origen, destino)
    print(f"Listo: {destino}\nCompletalo (o pedíselo a Claude con la skill buscaclientes) y después: clientes buscar {a.proyecto}")


def cmd_buscar(a) -> None:
    d, p = cargar_proyecto(a.proyecto)
    b = p["busqueda"]
    zonas = a.zonas or b["zonas"]
    terminos = a.terminos or b["terminos"]
    maximo = a.por_busqueda or b["por_busqueda"]
    resenas = b["resenas"] if a.resenas is None else a.resenas
    if not zonas:
        raise SystemExit("No hay zonas: completá busqueda.zonas en el perfil o pasá --zonas")
    cache = d / "cache"
    pend = [(t, z) for z in zonas for t in terminos
            if not apify.en_cache(cache, apify.clave_cache(t, z, maximo, resenas, b["contactos"], b["idioma"]))]
    total = len(zonas) * len(terminos)
    costo = len(pend) * maximo * apify.COSTO_POR_LUGAR
    print(f"{total} búsquedas ({len(pend)} nuevas, {total - len(pend)} en caché) · hasta {maximo} lugares cada una")
    if pend:
        try:
            usado, limite = apify.credito()
            print(f"Apify: usado USD {usado:.2f} de {limite:.2f} este mes")
        except Exception:
            pass
        if not confirmar(f"Costo estimado: hasta USD {costo:.2f}.", a.si):
            return
    leads = leer_leads(d)
    antes = len(leads)
    for z in zonas:
        for t in terminos:
            print(f"  · «{t}» en {z}", flush=True)
            res = apify.buscar(t, z, maximo, resenas, b["contactos"], b["idioma"], cache)
            for item in res["items"]:
                if not item.get("title") or item.get("permanentlyClosed"):
                    continue
                l = apify.normalizar(item, t, z)
                if l["id"] in leads:  # conserva notas e importaciones previas
                    l["notas"] = leads[l["id"]].get("notas", "")
                leads[l["id"]] = {**leads.get(l["id"], {}), **l}
    guardar_leads(d, leads)
    print(f"{len(leads) - antes} leads nuevos · {len(leads)} en total. Seguí con: clientes planilla {a.proyecto}")


def cmd_importar(a) -> None:
    """CSV con columnas (en cualquier orden): nombre, ciudad, instagram, telefono, email, web, notas, segmento, seguidores."""
    d, _ = cargar_proyecto(a.proyecto)
    leads = leer_leads(d)
    por_ig = {handle_ig(l.get("instagram", "")): k for k, l in leads.items() if l.get("instagram")}
    nuevos = unidos = 0
    with open(a.archivo, newline="", encoding="utf-8-sig") as fh:
        for fila in csv.DictReader(fh):
            f = {k.strip().lower(): (v or "").strip() for k, v in fila.items() if k}
            if not f.get("nombre"):
                continue
            ig = handle_ig(f.get("instagram", ""))
            seg = f.get("seguidores", "").replace(".", "")
            lead = {
                "id": f"lista:{ig or puntaje.norm(f['nombre'] + f.get('ciudad', ''))}",
                "origen": "Lista propia", "nombre": f["nombre"], "categoria": "", "categorias": [],
                "direccion": "", "ciudad": f.get("ciudad", ""), "telefono": f.get("telefono", ""),
                "web": f.get("web", ""), "maps": "", "rating": None, "cant_resenas": 0,
                "volumen": int(seg) // 300 if seg.isdigit() else 0,
                "emails": [e.strip() for e in f.get("email", "").split(",") if "@" in e],
                "instagram": ig, "resenas": [], "notas": f.get("notas", ""),
                "segmento_forzado": f.get("segmento") or None,
            }
            k = por_ig.get(ig) if ig else None
            if k:  # ya estaba en Maps: sumar lo que falta
                l = leads[k]
                l["notas"] = (l.get("notas", "") + "\n" + lead["notas"]).strip()
                l["telefono"] = l.get("telefono") or lead["telefono"]
                l["emails"] = l.get("emails") or lead["emails"]
                l["origen"] = "Maps + lista"
                l["segmento_forzado"] = l.get("segmento_forzado") or lead["segmento_forzado"]
                unidos += 1
            else:
                leads[lead["id"]] = {**leads.get(lead["id"], {}), **lead}
                nuevos += 1
    guardar_leads(d, leads)
    print(f"{nuevos} leads nuevos, {unidos} unidos con Google Maps · {len(leads)} en total")


def cmd_planilla(a) -> None:
    d, p = cargar_proyecto(a.proyecto)
    leads = list(leer_leads(d).values())
    if not leads:
        raise SystemExit(f"No hay leads. Primero: clientes buscar {a.proyecto}")
    segs = {s["id"]: s for s in p["segmentos"]}
    segs["general"] = p["segmento_general"]

    excluir = [puntaje.norm(x) for x in p["filtro"]["excluir"] if x]
    base = []
    for l in leads:
        if any(x and (x == puntaje.norm(handle_ig(l.get("instagram", ""))) or x in puntaje.norm(l.get("nombre", ""))) for x in excluir):
            continue
        l["_localidad"] = puntaje.localidad(l)
        seg, conteo = puntaje.segmento(l, p)
        pts, mot = puntaje.puntuar(l, p, conteo)
        base.append((l, seg, pts, mot))

    analisis: dict[str, dict] = {}
    if not a.sin_ia and ia.activa(p):
        candidatos = sorted((x for x in base if x[2] > 5), key=lambda x: x[2], reverse=True)[: p["ia"]["maximo"]]
        cache = d / "cache"
        sin_cache = [x for x in candidatos if not ia.archivo_cache(p, x[0], cache).exists()]
        costo = ia.costo_estimado(p, len(sin_cache))
        texto = f"IA ({p['ia']['modelo']}) sobre {len(candidatos)} leads ({len(sin_cache)} nuevos): hasta USD {costo:.2f}."
        if not sin_cache or confirmar(texto, a.si):
            cli = ia.cliente_nuevo()
            with ThreadPoolExecutor(max_workers=4) as ex:
                res = list(ex.map(lambda x: ia.analizar(cli, p, x[0], cache), candidatos))
            analisis = {x[0]["id"]: r for x, r in zip(candidatos, res) if r}
            print(f"IA: {len(analisis)} leads analizados")
    elif not a.sin_ia:
        print("Sin ANTHROPIC_API_KEY: puntaje por palabras clave y mensajes de plantilla (funciona igual).")

    filas = []
    for l, seg, pts, mot in base:
        an = analisis.get(l["id"])
        gancho = ""
        citas = ""
        if an:
            if not an["es_cliente_ideal"]:
                pts, mot = min(pts, 8), f"IA: {an['motivo']}"
            else:
                seg = segs.get(an["segmento"], seg)
                pts = max(0, min(100, pts + an["ajuste_puntaje"]))
                mot = f"{mot} · IA: {an['motivo']}"
                gancho = an["gancho"]
            citas = "\n".join(an.get("citas", []))
        if pts < p["planilla"]["minimo"]:
            continue
        visita = puntaje.visitable(l["_localidad"], p)
        sec = mensajes.secuencia(l, seg, p, visita, gancho)
        filas.append({
            **sec, "puntaje": pts, "nombre": l["nombre"], "ciudad": l["_localidad"], "segmento": seg["id"],
            "motivo": mot, "instagram": l.get("instagram", ""), "telefono": l.get("telefono", ""),
            "email": ", ".join(l.get("emails", [])), "citas": citas, "cant_resenas": l.get("cant_resenas") or None,
            "rating": l.get("rating"), "notas": l.get("notas", ""), "web": l.get("web", ""), "maps": l.get("maps", ""),
            "origen": l.get("origen", ""), "analisis": "IA" if an else "palabras",
        })
    filas.sort(key=lambda f: f["puntaje"], reverse=True)
    destino = d / "salidas" / f"{a.proyecto}.xlsx"
    planilla.guardar(filas, p, destino)
    alta = sum(1 for f in filas if f["puntaje"] >= p["planilla"]["prioridad_alta"])
    print(f"{len(filas)} leads ({alta} prioridad alta) → {destino} (+ .csv)")


def cmd_estado(a) -> None:
    d, _ = cargar_proyecto(a.proyecto)
    leads = list(leer_leads(d).values())
    from collections import Counter
    print(f"{len(leads)} leads")
    for k, v in Counter(l.get("origen", "") for l in leads).most_common():
        print(f"  {k}: {v}")
    print(f"  con email: {sum(1 for l in leads if l.get('emails'))} · con Instagram: {sum(1 for l in leads if l.get('instagram'))}"
          f" · con teléfono: {sum(1 for l in leads if l.get('telefono'))}")


def cmd_demo(_a) -> None:
    """Proyecto 'demo' con 12 negocios ficticios de Santiago y el perfil de bordados: no usa Apify ni IA."""
    d = DATOS / "demo"
    d.mkdir(parents=True, exist_ok=True)
    texto = (RAIZ / "perfiles" / "bordados-uniformes.yaml").read_text(encoding="utf-8")
    texto = texto.replace("bordamos para N empresas de Santiago", "bordamos para 40 empresas de Santiago (dato de la demo)")
    (d / "perfil.yaml").write_text(texto, encoding="utf-8")
    shutil.copy(RAIZ / "ejemplos" / "demo-leads.json", d / "leads.json")
    print("Demo: 12 negocios ficticios de Santiago, perfil de un taller de bordados.")
    cmd_planilla(argparse.Namespace(proyecto="demo", sin_ia=True, si=False))


def cmd_credito(_a) -> None:
    usado, limite = apify.credito()
    print(f"Apify: usado USD {usado:.2f} de {limite:.2f} este mes (quedan {limite - usado:.2f})")


def main(argv: list[str] | None = None) -> None:
    cargar_env()
    ap = argparse.ArgumentParser(prog="clientes", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("nuevo", help="crear un proyecto")
    s.add_argument("proyecto")
    s.add_argument("--desde", default="plantilla", help="perfil base de la carpeta perfiles/ (default: plantilla)")
    s.set_defaults(f=cmd_nuevo)

    s = sub.add_parser("buscar", help="buscar en Google Maps")
    s.add_argument("proyecto")
    s.add_argument("--zonas", nargs="+")
    s.add_argument("--terminos", nargs="+")
    s.add_argument("--por-busqueda", type=int)
    s.add_argument("--resenas", type=int)
    s.add_argument("--si", action="store_true", help="no preguntar por el costo")
    s.set_defaults(f=cmd_buscar)

    s = sub.add_parser("importar", help="sumar una lista propia en CSV")
    s.add_argument("proyecto")
    s.add_argument("archivo")
    s.set_defaults(f=cmd_importar)

    s = sub.add_parser("planilla", help="armar la planilla")
    s.add_argument("proyecto")
    s.add_argument("--sin-ia", action="store_true")
    s.add_argument("--si", action="store_true", help="no preguntar por el costo de la IA")
    s.set_defaults(f=cmd_planilla)

    s = sub.add_parser("estado", help="resumen de un proyecto")
    s.add_argument("proyecto")
    s.set_defaults(f=cmd_estado)

    s = sub.add_parser("credito", help="crédito de Apify")
    s.set_defaults(f=cmd_credito)

    s = sub.add_parser("demo", help="probar con negocios ficticios, sin token")
    s.set_defaults(f=cmd_demo)

    a = ap.parse_args(argv)
    a.f(a)
