"""Lectura de los datos publicados (data/publicado/): lo único que necesita el dashboard, local o en la nube."""
import json
import os
from pathlib import Path

import pandas as pd

RAIZ = Path(os.environ.get("DAILY_REPORTING_ROOT", Path(__file__).resolve().parent.parent)).resolve()
PUBLICADO = RAIZ / "data" / "publicado"

FECHAS_FACTURACION = ["f_cierre", "fec_aper"]
FECHAS_VENTA = ["fecha_cierre_ot", "fecha_documento"]
TEXTO_FACTURACION = ["tipo", "descripcion", "descripcion_1", "modelo", "motivo_de_entrada", "asesor"]
TEXTO_VENTA = ["codigo_parte", "tipo_or", "canal", "marca_vehiculo", "marca_repuesto", "documento", "descripcion"]


def leer_estado(publicado: Path = None) -> dict | None:
    ruta = (publicado or PUBLICADO) / "estado.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def fuente(estado: dict | None, archivo: str, publicado: Path = None):
    """Metadatos + ruta del CSV publicado de `archivo`, o None si no hay datos válidos publicados."""
    if not estado or archivo not in estado.get("archivos", {}):
        return None
    info = estado["archivos"][archivo]
    ruta = (publicado or PUBLICADO) / info["csv"]
    if not info.get("datos_publicados") or not ruta.exists():
        return None
    return dict(ruta=ruta, **info["datos_publicados"], ultimo_intento=info.get("ultimo_intento"))


def _leer(ruta: Path, fechas, textos) -> pd.DataFrame:
    columnas = pd.read_csv(ruta, nrows=0, encoding="utf-8-sig").columns
    return pd.read_csv(ruta, encoding="utf-8-sig", dtype={c: "string" for c in textos if c in columnas},
                       parse_dates=[c for c in fechas if c in columnas])


def leer_facturacion(ruta: Path) -> pd.DataFrame:
    return _leer(ruta, FECHAS_FACTURACION, TEXTO_FACTURACION)


def leer_venta_interna(ruta: Path) -> pd.DataFrame:
    return _leer(ruta, FECHAS_VENTA, TEXTO_VENTA)
