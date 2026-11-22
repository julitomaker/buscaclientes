FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY buscaclientes ./buscaclientes
COPY perfiles ./perfiles

# Los proyectos (perfil, leads, caché y planillas) viven en un volumen para no perderse
ENV BC_DATOS=/datos
VOLUME ["/datos"]

ENTRYPOINT ["python", "-m", "buscaclientes"]
CMD ["--help"]
