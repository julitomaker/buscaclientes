"""Planilla Excel + CSV con puntaje, contacto y la secuencia de mensajes de cada lead."""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

COLS = [
    ("Puntaje", "puntaje", 8), ("Nombre", "nombre", 30), ("Ciudad", "ciudad", 22), ("Segmento", "segmento", 15),
    ("Por qué", "motivo", 28), ("Modalidad", "modalidad", 16), ("Instagram", "instagram", 22),
    ("Teléfono", "telefono", 18), ("Email", "email", 28),
    ("Día 1 · Asunto", "asunto", 24), ("Día 1 · Email", "email1", 60),
    ("Día 4 · Seguimiento (mismo hilo)", "seguimiento", 55),
    ("DM Instagram (día 7, o día 1 si no hay mail)", "dm", 55),
    ("Día 11 · WhatsApp o llamado al equipo", "llamada", 55),
    ("Día 18 · Cierre (mismo hilo)", "cierre", 50),
    ("Citas de reseñas", "citas", 45), ("Reseñas", "cant_resenas", 9), ("Rating", "rating", 7),
    ("Notas", "notas", 40), ("Web", "web", 28), ("Google Maps", "maps", 28), ("Origen", "origen", 14),
    ("Análisis", "analisis", 10), ("Estado", None, 14), ("Próximo paso", None, 30),
]


def _guia(perfil: dict) -> list[str]:
    pp = perfil["planilla"]
    return [
        f"CÓMO USAR ESTA PLANILLA · {perfil['negocio']['nombre']}",
        "",
        f"Orden: arrancá por los verdes ({pp['prioridad_alta']}+). Máximo {pp['por_semana']} leads nuevos por semana, de a uno y revisando cada mensaje.",
        "Mandá los mails martes o miércoles a primera hora. Evitá el viernes.",
        "",
        "LA SECUENCIA (3 semanas, 5 contactos, después se frena)",
        "Día 1 · Email. Texto plano, sin imágenes ni varios links. Si no tiene mail, arrancá por el DM.",
        "Día 2 · Instagram: seguilo y dale like a un posteo reciente. Ese día NO le escribas.",
        "Día 4 · Respondé en el MISMO hilo del mail con el seguimiento.",
        "Día 7 · DM de Instagram.",
        "Día 11 · WhatsApp o llamado: hablá con quien maneja la agenda (secretaria, recepción, encargado).",
        "Día 18 · Cierre en el mismo hilo. Sin respuesta: 'no por ahora' y se retoma en 3 meses.",
        "Si responde en cualquier punto, cortá la secuencia y seguí la charla a mano.",
        "",
        "ANTES DE MANDAR",
        "Leé el mensaje entero. El saludo y el segmento salen de la ficha pública: si algo no le corresponde, corregilo.",
        "Si el nombre es de un local o una clínica, cambiá el saludo por el nombre de la persona si lo conseguís.",
        "",
        "CUIDADOS",
        "Nada de envíos masivos por WhatsApp ni desde el número de un bot: Meta bloquea números que reciben denuncias.",
        "Pocos mails, personalizados y desde una casilla real. Si alguien pide que no le escriban, se lo saca de la lista.",
        "Revisá las reglas de tu rubro antes de ofrecer comisiones o beneficios a profesionales (salud, gobierno, etc.).",
        "No prometas resultados que no puedas demostrar. Los datos de prueba social tienen que ser reales.",
        "",
        "ESTADOS: nuevo → contactado → respondió → reunión/visita → evaluando → cliente → no por ahora",
    ]


def guardar(filas: list[dict], perfil: dict, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    pp = perfil["planilla"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Leads"
    ws.append([c for c, _, _ in COLS])
    for i, (_, _, ancho) in enumerate(COLS, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = ancho
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F2A3A")
    for f in filas:
        ws.append([(f.get(k) if k else ("nuevo" if t == "Estado" else "")) for t, k, _ in COLS])
    for fila in ws.iter_rows(min_row=2):
        for c in fila:
            c.alignment = Alignment(wrap_text=True, vertical="top")
        p = fila[0].value or 0
        color = "C8E6C9" if p >= pp["prioridad_alta"] else "FFF3C4" if p >= pp["prioridad_media"] else "EEEEEE"
        fila[0].fill = PatternFill("solid", fgColor=color)
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    g = wb.create_sheet("Cómo usarla")
    for linea in _guia(perfil):
        g.append([linea])
    g.column_dimensions["A"].width = 140
    wb.save(destino)

    with destino.with_suffix(".csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow([c for c, k, _ in COLS if k])
        for f in filas:
            w.writerow([f.get(k, "") for _, k, _ in COLS if k])
