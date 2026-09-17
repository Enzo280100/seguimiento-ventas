"""Preparación automática: Excel de data/originales -> CSV validados.

Hace el mismo trabajo que notebooks/01_preparacion.ipynb (modo completo), sin intervención manual:
lee, normaliza nombres, convierte tipos sin perder valores, valida (filas, fechas, clave, historia sin cambios),
guarda en data/preparados/ (historial local) y, solo si todo pasa, publica en data/publicado/ lo que usa el dashboard.

Solo reprocesa un archivo si cambió su contenido (hash). Uso: `python actualizar.py` o automáticamente desde app.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ARCHIVOS, VERSION


# ============================ Rutas y registro ============================

class Rutas:
    def __init__(self, raiz=None):
        self.raiz = Path(raiz or os.environ.get("DAILY_REPORTING_ROOT", Path(__file__).resolve().parent.parent)).resolve()
        self.originales = self.raiz / "data" / "originales"
        self.preparados = self.raiz / "data" / "preparados"
        self.publicado = self.raiz / "data" / "publicado"
        self.registro = self.preparados / "registro_preparacion.jsonl"
        self.resumen = self.preparados / "resumen_preparacion.md"
        self.estado = self.publicado / "estado.json"

    def rel(self, p: Path) -> str:
        return p.relative_to(self.raiz).as_posix()


def hay_originales(raiz=None) -> bool:
    r = Rutas(raiz)
    return any((r.originales / n).exists() for n in ARCHIVOS)


def leer_registro(rutas: Rutas) -> list[dict]:
    if not rutas.registro.exists():
        return []
    with open(rutas.registro, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _agregar_registro(rutas: Rutas, entrada: dict):
    rutas.preparados.mkdir(parents=True, exist_ok=True)
    with open(rutas.registro, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entrada, ensure_ascii=False, default=str) + "\n")


def _ultima(historial, archivo, estado=None):
    for e in reversed(historial):
        if e.get("archivo") == archivo and e.get("version") == VERSION and (estado is None or e.get("estado") == estado):
            return e
    return None


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


# ============================ Normalización y tipos ============================

def normalizar_texto(nombre) -> str:
    s = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode()
    return re.sub(r"[^0-9a-zA-Z]+", "_", s.strip().lower()).strip("_")


def normalizar_columnas(columnas):
    """Nombres snake_case únicos; columnas sin nombre -> unknown_<n>."""
    nuevos, sin_nombre, usados = [], [], set()
    for i, c in enumerate(columnas):
        vacio = c is None or (isinstance(c, float) and np.isnan(c)) or str(c).strip() == "" or str(c).startswith("Unnamed:")
        base = f"unknown_{i}" if vacio else (normalizar_texto(c) or f"unknown_{i}")
        n, k = base, 1
        while n in usados:
            n, k = f"{base}_{k}", k + 1
        usados.add(n)
        nuevos.append(n)
        if base.startswith("unknown_"):
            sin_nombre.append(n)
    return nuevos, sin_nombre


def _presentes(s):
    return s.notna() & (s.astype(str).str.strip() != "")


def convertir_fecha(s: pd.Series, dayfirst=True):
    """Devuelve (serie datetime64, n_valores_no_convertibles)."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s.astype("datetime64[ns]"), 0
    pres = _presentes(s)
    res = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    es_dt = s.map(lambda v: isinstance(v, (datetime, pd.Timestamp))) & pres
    if es_dt.any():
        res.loc[es_dt] = pd.to_datetime(s[es_dt])
    num = pd.to_numeric(s.where(~es_dt), errors="coerce")
    serial = pres & ~es_dt & num.between(20000, 80000)
    if serial.any():
        res.loc[serial] = pd.to_datetime(num[serial], unit="D", origin="1899-12-30")
    txt = s[pres & ~es_dt & ~serial].astype(str).str.strip()
    txt = txt[txt.str.match(r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}")]
    if len(txt):
        iso = txt.str.match(r"^\d{4}[-/.]")
        if iso.any():
            res.loc[txt[iso].index] = pd.to_datetime(txt[iso], format="mixed", dayfirst=False, errors="coerce")
        if (~iso).any():
            res.loc[txt[~iso].index] = pd.to_datetime(txt[~iso], format="mixed", dayfirst=dayfirst, errors="coerce")
    return res, int((pres & res.isna()).sum())


def convertir_numero(s: pd.Series):
    """Devuelve (serie numérica, n_valores_no_convertibles). Acepta 'S/ 1,234.50', '(100)', coma decimal."""
    if pd.api.types.is_numeric_dtype(s):
        return s, 0
    pres = _presentes(s)
    es_num = s.map(lambda v: isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)) & pres
    res = pd.Series(np.nan, index=s.index, dtype="float64")
    res.loc[es_num] = s[es_num].astype(float)
    txt = s[pres & ~es_num].astype(str).str.strip()
    if len(txt):
        limpio = txt.str.replace(r"(US\$|S/\.?|\$|€|%|\s)", "", flags=re.I, regex=True)
        negativo = limpio.str.fullmatch(r"\(.+\)")
        limpio = limpio.str.strip("()")
        coma = limpio.str.fullmatch(r"-?\d{1,3}(\.\d{3})+(,\d+)?|-?\d+,\d+").sum()
        punto = limpio.str.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?|-?\d+\.\d+").sum()
        if coma > punto:
            limpio = limpio.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        else:
            limpio = limpio.str.replace(",", "", regex=False)
        val = pd.to_numeric(limpio, errors="coerce")
        val[negativo] = -val[negativo].abs()
        res.loc[val.index] = val
    return res, int((pres & res.isna()).sum())


def a_texto(s: pd.Series) -> pd.Series:
    """Texto conservando el valor (códigos numéricos de Excel sin '.0')."""
    def conv(v):
        if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA:
            return pd.NA
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        if isinstance(v, (datetime, pd.Timestamp)):
            return pd.Timestamp(v).isoformat()
        return str(v)
    return s.map(conv).astype("string")


def huella(df: pd.DataFrame) -> str:
    """Hash independiente del orden de filas y estable entre ejecuciones (tipos canónicos)."""
    if df.empty:
        return "0"
    canon = df.copy()
    for c in canon.columns:
        if pd.api.types.is_numeric_dtype(canon[c]):
            canon[c] = canon[c].astype("float64")
    return str(int(pd.util.hash_pandas_object(canon, index=False).sum() % (1 << 64)))


# ============================ Proceso por archivo ============================

def procesar_archivo(nombre: str, cfg: dict, rutas: Rutas, historial: list, aceptar_cambios_historia=False, hoy=None) -> dict:
    ruta = rutas.originales / nombre
    hoy = pd.Timestamp(hoy or pd.Timestamp.today()).normalize()
    entrada = dict(momento=datetime.now().isoformat(timespec="seconds"), version=VERSION, modo="automatico",
                   archivo=nombre, indicador=cfg["indicador"], origen_sha256=sha256(ruta), estado="ERROR",
                   salida=None, publicado=None, validaciones_fallidas=[], transformaciones=[], mensaje="")
    trans = entrada["transformaciones"]

    try:
        crudo = pd.read_excel(ruta, sheet_name=cfg["hoja"], header=cfg["fila_encabezado"])
    except Exception as e:   # tipo y mensaje, sin datos
        entrada["mensaje"] = f"{type(e).__name__}: {e}"
        return entrada
    trans.append(f"lectura: hoja '{cfg['hoja']}', encabezado fila {cfg['fila_encabezado']}, {len(crudo)} filas")
    crudo.columns, sin_nombre = normalizar_columnas(list(crudo.columns))
    trans.append("nombres de columna a snake_case sin tildes")

    requeridas = cfg["fechas"] + cfg["numeros"] + cfg["textos"]
    faltan = [c for c in requeridas if c not in crudo.columns]
    df = crudo[[c for c in requeridas if c in crudo.columns]].copy()

    fallos = {}
    for c in cfg["fechas"]:
        if c in df:
            df[c], f = convertir_fecha(df[c])
            fallos[c] = f
    for c in cfg["numeros"]:
        if c in df:
            num, f = convertir_numero(df[c])
            num = pd.to_numeric(num)
            enteros = num.dropna()
            df[c] = num.astype("Int64") if len(enteros) and (enteros == enteros.round()).all() else num.astype("float64")
            fallos[c] = f
    for c in cfg["textos"]:
        if c in df:
            df[c] = a_texto(df[c])
    con_fallos = {c: n for c, n in fallos.items() if n}
    trans.append("tipos: fechas a datetime, números a numérico, textos a texto (sin eliminar ni imputar)")

    checks = []
    def chk(nombre_chk, ok, detalle=""):
        checks.append(dict(validacion=nombre_chk, ok=bool(ok), detalle=str(detalle)))

    chk("columnas requeridas presentes", not faltan, f"faltan: {faltan}" if faltan else "")
    chk("filas > 0", len(df) > 0, f"{len(df):,} filas")
    chk("conversiones de tipo sin pérdida", not con_fallos, f"no convertibles: {con_fallos}" if con_fallos else "")
    col = cfg["col_fecha"]
    fechas = df[col].dt.normalize() if col in df else pd.Series(dtype="datetime64[ns]")
    chk(f"fecha principal ({col}) sin nulos", col in df and fechas.notna().all(), f"nulos={int(fechas.isna().sum())}")
    futuras, antiguas = int((fechas > hoy).sum()), int((fechas < "2000-01-01").sum())
    chk("fechas en rango plausible", futuras == 0 and antiguas == 0, f"futuras={futuras}, <2000={antiguas}")
    if cfg["clave"]:
        presentes = all(c in df for c in cfg["clave"])
        dup = int(df.duplicated(subset=cfg["clave"], keep=False).sum()) if presentes else -1
        nul = int(df[cfg["clave"]].isna().any(axis=1).sum()) if presentes else -1
        chk("clave única y sin nulos", presentes and dup == 0 and nul == 0, f"clave={cfg['clave']}, repetidas={dup}, nulos={nul}")
    if sin_nombre:
        trans.append(f"columnas sin nombre ignoradas: {sin_nombre}")

    previo = _ultima(historial, nombre, "COMPLETO")
    fecha_min = fechas.min() if len(fechas.dropna()) else None
    fecha_max = fechas.max() if len(fechas.dropna()) else None
    if previo and not faltan and fecha_max is not None:
        prev_max = pd.Timestamp(previo["fecha_max"])
        hasta = df[fechas <= prev_max]
        if aceptar_cambios_historia:
            trans.append("validación de historia omitida: cambios aceptados por el usuario")
        else:
            chk("historia: mismas columnas", previo["columnas"] == list(df.columns))
            chk("historia: fecha máxima no retrocede", fecha_max >= prev_max, f"{prev_max.date()} -> {fecha_max.date()}")
            chk("historia: mismas filas hasta la fecha anterior", len(hasta) == previo["filas"], f"antes {previo['filas']:,}, ahora {len(hasta):,}")
            chk("historia: mismos valores hasta la fecha anterior", huella(hasta) == previo["huella"])

    fallidas = [c["validacion"] for c in checks if not c["ok"]]
    entrada.update(
        estado="COMPLETO" if not fallidas else "PARCIAL", validaciones=checks, validaciones_fallidas=fallidas,
        filas=len(df), columnas=list(df.columns), col_fecha=col,
        fecha_min=None if fecha_min is None else str(fecha_min.date()),
        fecha_max=None if fecha_max is None else str(fecha_max.date()),
        huella=huella(df) if not fallidas else None,
    )

    if entrada["estado"] == "COMPLETO":
        # historial local (data/preparados): no sobrescribe versiones distintas del mismo período
        rutas.preparados.mkdir(parents=True, exist_ok=True)
        base = f"{cfg['indicador']}_hasta_{fecha_max:%Y%m%d}"
        destino, k = rutas.preparados / f"{base}.csv", 1
        mismas = {e.get("salida"): e.get("huella") for e in historial if e.get("estado") == "COMPLETO"}
        while destino.exists() and mismas.get(rutas.rel(destino)) != entrada["huella"]:
            k += 1
            destino = rutas.preparados / f"{base}_v{k}.csv"
        if not destino.exists():
            df.to_csv(destino, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d %H:%M:%S")
        entrada["salida"] = rutas.rel(destino)

        # publicación (lo que lee el dashboard): solo columnas acordadas, sin datos personales
        rutas.publicado.mkdir(parents=True, exist_ok=True)
        pub = rutas.publicado / cfg["publicar"]
        tmp = pub.with_suffix(".tmp")
        df[cfg["columnas_publicadas"]].to_csv(tmp, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d %H:%M:%S")
        filas_csv = len(pd.read_csv(tmp, usecols=[0], encoding="utf-8-sig"))
        if filas_csv != len(df):
            tmp.unlink()
            entrada.update(estado="PARCIAL", validaciones_fallidas=["filas escritas = filas preparadas"],
                           mensaje=f"{filas_csv} filas escritas vs {len(df)}")
            return entrada
        os.replace(tmp, pub)
        entrada["publicado"] = rutas.rel(pub)
        trans.append(f"publicado {entrada['publicado']} ({filas_csv:,} filas verificadas)")
    return entrada


# ============================ Orquestación ============================

def preparar(raiz=None, forzar=False, aceptar_cambios_historia=False, hoy=None) -> dict:
    """Procesa los archivos cuyo contenido cambió. Devuelve {archivo: resultado}."""
    rutas = Rutas(raiz)
    historial = leer_registro(rutas)
    resultados, hubo_cambios = {}, False
    for nombre, cfg in ARCHIVOS.items():
        ruta = rutas.originales / nombre
        if not ruta.exists():
            resultados[nombre] = dict(archivo=nombre, estado="FALTA", reprocesado=False,
                                      mensaje=f"No existe data/originales/{nombre}")
            continue
        ultimo = _ultima(historial, nombre)
        if ultimo and not forzar and not aceptar_cambios_historia and ultimo.get("origen_sha256") == sha256(ruta):
            resultados[nombre] = dict(ultimo, reprocesado=False)
            continue
        entrada = procesar_archivo(nombre, cfg, rutas, historial, aceptar_cambios_historia, hoy)
        _agregar_registro(rutas, entrada)
        historial.append(entrada)
        resultados[nombre] = dict(entrada, reprocesado=True)
        hubo_cambios = True
    if hubo_cambios or not rutas.estado.exists():
        escribir_estado(rutas, historial)
        escribir_resumen(rutas, resultados)
    return resultados


def escribir_estado(rutas: Rutas, historial: list):
    """data/publicado/estado.json: último intento y últimos datos publicados válidos por archivo."""
    estado = dict(generado=datetime.now().isoformat(timespec="seconds"), archivos={})
    for nombre, cfg in ARCHIVOS.items():
        ultimo, valido = _ultima(historial, nombre), _ultima(historial, nombre, "COMPLETO")
        estado["archivos"][nombre] = dict(
            indicador=cfg["indicador"], csv=cfg["publicar"],
            ultimo_intento=None if not ultimo else dict(
                momento=ultimo["momento"], estado=ultimo["estado"],
                validaciones_fallidas=ultimo.get("validaciones_fallidas", []), mensaje=ultimo.get("mensaje", "")),
            datos_publicados=None if not valido else dict(
                preparado=valido["momento"], fecha_min=valido["fecha_min"], fecha_max=valido["fecha_max"],
                filas=valido["filas"], col_fecha=valido["col_fecha"]),
        )
    rutas.publicado.mkdir(parents=True, exist_ok=True)
    rutas.estado.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")


def escribir_resumen(rutas: Rutas, resultados: dict):
    lineas = ["# Resumen de preparación (automática)", "", f"- Generado: {datetime.now().isoformat(timespec='minutes')}", ""]
    for nombre, r in resultados.items():
        lineas += [f"## {nombre} — `{r.get('estado')}`" + ("" if r.get("reprocesado") else " (sin cambios)"), ""]
        for k in ("filas", "fecha_min", "fecha_max", "salida", "publicado", "mensaje"):
            if r.get(k) not in (None, ""):
                lineas.append(f"- {k}: {r[k]}")
        if r.get("validaciones"):
            lineas += ["", "| validación | ok | detalle |", "|---|---|---|"]
            lineas += [f"| {v['validacion']} | {'✅' if v['ok'] else '❌'} | {v['detalle']} |" for v in r["validaciones"]]
        if r.get("transformaciones"):
            lineas += ["", "Transformaciones:"] + [f"- {t}" for t in r["transformaciones"]]
        lineas.append("")
    rutas.preparados.mkdir(parents=True, exist_ok=True)
    rutas.resumen.write_text("\n".join(lineas), encoding="utf-8")
