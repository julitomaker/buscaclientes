---
name: buscaclientes
description: Buscar clientes para un negocio en Google Maps (B2B), puntuarlos y dejar armada una secuencia de contacto en frío (mail, DM de Instagram, llamado o WhatsApp al equipo, visita o envío de muestra) en una planilla Excel. Usa la herramienta `clientes` (Apify + IA opcional de Claude). Usala SIEMPRE que alguien pida conseguir clientes, armar una base de datos o lista de prospectos, buscar negocios o profesionales de un rubro y zona (clínicas, restaurantes, gimnasios, estudios, cirujanos, colegios, comercios), hacer algo «tipo Mapileads», sacar emails o teléfonos de Google Maps, o preparar mensajes de primer contacto a empresas. También para instalar la herramienta en una VPS o en la nube.
---

# Buscaclientes

La herramienta busca negocios en Google Maps con Apify, lee sus reseñas, les pone un puntaje según el perfil del negocio que vende y arma, para cada uno, cinco mensajes listos para revisar y mandar a mano. Nunca manda nada sola.

## Dónde está y cómo se corre

Buscá el script `clientes` (carpeta del repo `buscaclientes`, o `~/.local/bin/clientes`). Si no está instalado: `git clone https://github.com/julitomaker/buscaclientes.git && cd buscaclientes && ./instalar.sh` (o Docker: `docker compose run --rm clientes ...`). Para mostrar cómo queda sin gastar nada: `clientes demo`.

```
clientes nuevo <proyecto> [--desde plantilla|fajas-cirujanos|bordados-uniformes]
clientes buscar <proyecto> [--zonas "Ciudad, País" ...] [--terminos ...] [--por-busqueda N] [--resenas N] [--si]
clientes importar <proyecto> lista.csv     # nombre, ciudad, instagram, telefono, email, web, notas, segmento, seguidores
clientes planilla <proyecto> [--sin-ia] [--si]
clientes estado <proyecto>
clientes credito
clientes demo                              # planilla de prueba con negocios ficticios, sin token
```

Cada proyecto vive en `proyectos/<proyecto>/`: `perfil.yaml`, `leads.json` (se acumula entre búsquedas), `cache/` (lo ya buscado no se vuelve a cobrar) y `salidas/<proyecto>.xlsx` + `.csv`.

## El flujo

### 1. Armar el perfil con la persona (lo más importante)

Creá el proyecto con `clientes nuevo` y completá `perfil.yaml` entrevistando a la persona. No inventes datos: si no lo sabés, preguntá. Preguntas, de a pocas:

1. Qué vendés y a quién. Qué gana tu cliente con vos, en una línea (`negocio.presentacion`).
2. Cómo lo buscarías en Google Maps (2 o 3 términos) y en qué ciudades o barrios (`busqueda`).
3. Qué tipos de cliente hay dentro del rubro y cuál es el mejor. Para cada tipo: qué palabras lo delatan en sus reseñas o su nombre, qué le ofrecerías distinto (`segmentos`, en orden de prioridad).
4. Qué NO es cliente: categorías a descartar, franquicias, clientes actuales a excluir (`filtro`).
5. Un dato real de prueba social (cuántos clientes, desde cuándo, quiénes). Si no hay un número cierto, dejalo genérico. Nunca lo infles.
6. Qué ofrecés para empezar sin compromiso: muestra, visita de 10 minutos, simulación, prueba gratis. En qué zonas podés ir en persona (`ofrecimiento.zonas_visita`) y qué ofrecés a los de lejos (`remoto`).
7. Quién firma y con qué tono. Trato de usted o de vos.

Basate en `perfiles/plantilla.yaml` y mirá `perfiles/fajas-cirujanos.yaml` como ejemplo completo. Las plantillas de mensajes por defecto ya siguen las buenas prácticas de abajo: tocá `mensajes:` solo si la persona lo pide.

### 2. Buscar (cuesta plata: confirmá antes)

`clientes buscar` estima el costo y pregunta antes de gastar. Pasale el número a la persona y esperá su sí; recién ahí usá `--si`. Referencia: unos USD 0,02 por lugar con 15 reseñas y contactos. El plan gratis de Apify trae USD 5 por mes, o sea unos 200 lugares. Empezá con una zona chica (`--por-busqueda 10`) y mirá la calidad antes de ampliar.

Si tiene una lista propia (seguidores, una feria, contactos de Instagram), sumala con `clientes importar`.

### 3. Planilla

`clientes planilla`. Con `ANTHROPIC_API_KEY` en `.env`, la IA lee cada lead, descarta los que no sirven, ajusta el puntaje y escribe una frase de apertura personal. También estima el costo y pregunta antes. Sin clave funciona igual, con palabras clave y plantillas.

Después revisá la planilla con la persona:
- Los 10 primeros: tienen sentido? Si no, ajustá segmentos, palabras o penalizaciones en el perfil y volvé a correr `planilla` (no vuelve a cobrar Apify).
- Leé varios mensajes enteros. Saludos raros (nombre de clínica en vez de persona), segmentos mal elegidos o datos dudosos se corrigen en el perfil, no a mano en cada fila.

### 4. Contacto (lo hace la persona)

La herramienta no envía. Si te piden mandar algo en nombre de alguien, mostrá el texto exacto y esperá su sí, uno por uno.

## Buenas prácticas que ya trae (y por qué)

Salen de estudios de cold email B2B (Hunter, Gong, Lavender, Instantly) y de cómo venden los representantes de equipamiento médico. Son puntos de partida, no leyes: medí.

- **Primer mail de 50 a 80 palabras**, texto plano, sin imágenes. Abre con algo específico del lead, presenta en una línea y cierra con **una sola pregunta de interés** («Le interesaría que…?»). Pedir interés rinde más que pedir una reunión.
- **Asunto de 2 o 3 palabras**, descriptivo, sin signos, emojis ni el nombre de la persona.
- **5 contactos en 3 semanas y se frena:** mail (día 1) → seguir y dar like en Instagram (día 2) → seguimiento en el mismo hilo con prueba social y oferta concreta (día 4) → DM (día 7) → llamado o WhatsApp a quien maneja la agenda (día 11) → cierre amable (día 18).
- **Pocos y personalizados:** 10 a 15 leads nuevos por semana. Las campañas chicas responden más del doble que las masivas.
- **Martes o miércoles temprano.** Evitar el viernes.
- **La secretaria o recepción es la puerta.** Pedile 10 minutos como si fuera un turno.
- **Oferta sin compromiso:** muestra, visita corta o simulación. Baja la barrera.

## Cuidados (decíselos a la persona)

- **WhatsApp:** nada de envíos masivos ni en frío desde el número de un bot o de la API oficial. Meta baja la calidad del número y lo bloquea si recibe denuncias. A mano, de a uno, y mejor después de un primer contacto.
- **Profesionales de la salud y funcionarios:** en muchos países está prohibido pagarles comisión por derivar o recetar (en Argentina, Ley 17.132 art. 20). El beneficio va para el paciente o cliente final, nunca para el profesional. Ante la duda, abogado.
- **Datos personales y spam:** usar solo datos públicos de negocios, sacar de la lista a quien pida no recibir más, y mandar desde una casilla real con nombre y firma.
- **Promesas:** nada que no se pueda demostrar. Nada de antes y después ni resultados garantizados.
- **Costos:** Apify y la IA se cobran. Siempre estimá y confirmá antes de correr.

## Problemas comunes

- `Falta APIFY_TOKEN`: completar `.env` (console.apify.com → Settings → API & Integrations).
- Muchos leads fuera del rubro: completar `filtro.categorias_si` con partes de la categoría de Google Maps (por ejemplo `[cirug, plástic]`).
- Todos caen en «general»: faltan palabras en los segmentos, o el `minimo` es muy alto.
- Ciudad mal y modalidad equivocada: revisar `ofrecimiento.zonas_visita`, que son partes de texto de la localidad (`[palermo, caba, "san isidro"]`).
- En Ubuntu sin `python3-venv`, `instalar.sh` instala las librerías en `./lib` sin tocar el sistema.
