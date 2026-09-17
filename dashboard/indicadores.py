"""Cálculo de indicadores. Funciones puras: reciben DataFrames, no leen archivos ni usan Streamlit."""
from __future__ import annotations

import numpy as np
import pandas as pd

COLUMNAS_FACTURACION = ("referencia", "f_cierre", "tipo", "monto_ot")
COLUMNAS_VENTA = ("fecha_cierre_ot", "codigo_parte", "tipo_or", "canal", "marca_vehiculo", "marca_repuesto",
                  "valor_neto_sin_impuestos")
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
TIPOS_DIA = ["Lunes a viernes", "Sábado", "Domingo o feriado"]


# ============================ Calendario ============================

def dias_habiles(inicio, fin, feriados, laborables) -> pd.DatetimeIndex:
    """Días entre inicio y fin (inclusive) que son laborables y no feriados."""
    rango = pd.date_range(pd.Timestamp(inicio).normalize(), pd.Timestamp(fin).normalize(), freq="D")
    feriados_ts = pd.DatetimeIndex([pd.Timestamp(f) for f in feriados])
    return rango[rango.dayofweek.isin(laborables) & ~rango.isin(feriados_ts)]


def tipo_de_dia(fechas, feriados) -> np.ndarray:
    f = pd.DatetimeIndex(fechas)
    feriado = f.isin(pd.DatetimeIndex([pd.Timestamp(x) for x in feriados]))
    return np.select([feriado | (f.dayofweek == 6), f.dayofweek == 5], ["Domingo o feriado", "Sábado"], "Lunes a viernes")


def _norm(s: pd.Series) -> pd.Series:
    """Texto sin espacios extremos, en mayúsculas; vacío -> <NA>."""
    t = s.astype("string").str.strip().str.upper()
    return t.mask(t == "")


# ============================ Facturación ============================

def preparar_facturacion(df: pd.DataFrame, tipos_excluidos) -> pd.DataFrame:
    """Normaliza fecha y tipo, y marca las filas excluidas de la facturación."""
    faltan = [c for c in COLUMNAS_FACTURACION if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en los datos de facturación: {faltan}")
    out = df.copy()
    out["fecha"] = pd.to_datetime(out["f_cierre"]).dt.normalize()
    out["tipo_norm"] = _norm(out["tipo"])
    out["monto_ot"] = pd.to_numeric(out["monto_ot"])
    out["excluida"] = out["tipo_norm"].isin([t.upper() for t in tipos_excluidos])
    return out


def resumen_facturacion(df: pd.DataFrame, fecha_corte, meta, feriados, laborables,
                        umbral_en_meta=1.0, umbral_atencion=0.9, factor_ritmo=1.2) -> dict:
    """Facturación del mes de `fecha_corte` hasta ese día. `df` debe venir de `preparar_facturacion`."""
    corte = pd.Timestamp(fecha_corte).normalize()
    inicio_mes = corte.replace(day=1)
    fin_mes = inicio_mes + pd.offsets.MonthEnd(0)

    mes = df[(df["fecha"] >= inicio_mes) & (df["fecha"] <= corte)]
    incl = mes[~mes["excluida"]]
    excl = mes[mes["excluida"]]
    dia = incl[incl["fecha"] == corte]

    acumulado = float(incl["monto_ot"].sum())
    monto_dia = float(dia["monto_ot"].sum())

    habiles_mes = dias_habiles(inicio_mes, fin_mes, feriados, laborables)
    transcurridos = habiles_mes[habiles_mes <= corte]
    n_mes, n_trans = len(habiles_mes), len(transcurridos)
    n_rest = n_mes - n_trans

    esperado = meta * n_trans / n_mes if n_mes else 0.0
    pct_esperado = acumulado / esperado if esperado > 0 else None
    if pct_esperado is None:
        estado = "Sin referencia"
    elif pct_esperado >= umbral_en_meta:
        estado = "En meta"
    elif pct_esperado >= umbral_atencion:
        estado = "Atención"
    else:
        estado = "Atrasado"

    falta = max(meta - acumulado, 0.0)
    necesario = falta / n_rest if n_rest else None
    promedio = acumulado / n_trans if n_trans else None
    alerta_ritmo = bool(necesario is not None and promedio is not None and necesario > factor_ritmo * promedio)

    fechas_con_datos = set(mes["fecha"])   # cualquier fila del archivo, incluidas o excluidas
    sin_datos = [d for d in transcurridos if d not in fechas_con_datos]

    return dict(
        inicio_mes=inicio_mes, fin_mes=fin_mes, fecha_corte=corte, meta=float(meta),
        acumulado=acumulado, pct_meta=acumulado / meta if meta else None,
        monto_dia=monto_dia, ots_dia=int(dia["referencia"].nunique()),
        aporte_dia=monto_dia / acumulado if acumulado > 0 else None,
        ots_mes=int(incl["referencia"].nunique()),
        habiles_mes=n_mes, habiles_transcurridos=n_trans, habiles_restantes=n_rest,
        corte_es_habil=corte in habiles_mes,
        esperado=esperado, pct_esperado=pct_esperado, estado=estado,
        falta=falta, necesario_por_dia=necesario, promedio_por_dia_habil=promedio, alerta_ritmo=alerta_ritmo,
        # controles
        excluidas_filas=len(excl), excluidas_monto=float(excl["monto_ot"].sum()),
        excluidas_por_tipo=excl.groupby("tipo_norm")["monto_ot"].agg(["size", "sum"]).to_dict("index"),
        tipo_vacio_filas=int(incl["tipo_norm"].isna().sum()),
        negativos_filas=int((incl["monto_ot"] < 0).sum()), negativos_monto=float(incl.loc[incl["monto_ot"] < 0, "monto_ot"].sum()),
        ceros_filas=int((incl["monto_ot"] == 0).sum()),
        habiles_sin_datos=sin_datos,
        referencias_repetidas=int(mes["referencia"].duplicated().sum()),
        fecha_min_datos=df["fecha"].min(), fecha_max_datos=df["fecha"].max(),
    )


def serie_facturacion(df: pd.DataFrame, fecha_corte, meta, feriados, laborables) -> pd.DataFrame:
    """Una fila por día calendario del mes: monto y OTs (hasta el corte), acumulado real y esperado."""
    corte = pd.Timestamp(fecha_corte).normalize()
    inicio = corte.replace(day=1)
    fin = inicio + pd.offsets.MonthEnd(0)
    dias = pd.date_range(inicio, fin, freq="D")
    incl = df[~df["excluida"] & (df["fecha"] >= inicio) & (df["fecha"] <= corte)]
    g = incl.groupby("fecha").agg(monto=("monto_ot", "sum"), ots=("referencia", "nunique"))
    s = pd.DataFrame(index=dias).join(g)
    hasta_corte = s.index <= corte
    s.loc[hasta_corte] = s.loc[hasta_corte].fillna(0)
    s["ots"] = s["ots"].astype("Int64")
    s["acumulado"] = s["monto"].cumsum().where(hasta_corte)
    habiles = dias_habiles(inicio, fin, feriados, laborables)
    s["es_habil"] = s.index.isin(habiles)
    s["esperado_acumulado"] = meta * s["es_habil"].cumsum() / max(len(habiles), 1)
    s["tipo_dia"] = tipo_de_dia(s.index, feriados)
    s.index.name = "fecha"
    return s.reset_index()


# ============================ Patrones (facturación) ============================

def filas_periodo(df: pd.DataFrame, inicio, corte, incluir_excluidas=False) -> pd.DataFrame:
    m = (df["fecha"] >= pd.Timestamp(inicio)) & (df["fecha"] <= pd.Timestamp(corte))
    if not incluir_excluidas:
        m &= ~df["excluida"]
    return df[m]


def tabla_por_dia(incl: pd.DataFrame, inicio, corte, feriados) -> pd.DataFrame:
    """Todos los días calendario del período, con monto y N.º de OTs (0 si no hubo)."""
    dias = pd.date_range(pd.Timestamp(inicio), pd.Timestamp(corte), freq="D")
    g = incl.groupby("fecha").agg(monto=("monto_ot", "sum"), ots=("referencia", "nunique"))
    t = pd.DataFrame(index=dias).join(g).fillna({"monto": 0, "ots": 0})
    t["ots"] = t["ots"].astype(int)
    t["monto_por_ot"] = (t["monto"] / t["ots"]).where(t["ots"] > 0)
    t["tipo_dia"] = tipo_de_dia(t.index, feriados)
    t["dia_semana"] = [DIAS_SEMANA[d] for d in t.index.dayofweek]
    t.index.name = "fecha"
    return t.reset_index()


def resumen_tipo_dia(por_dia: pd.DataFrame, min_dias=4) -> pd.DataFrame:
    g = (por_dia.groupby("tipo_dia")
         .agg(dias=("fecha", "size"), monto=("monto", "sum"), ots=("ots", "sum"))
         .reindex(TIPOS_DIA).dropna(subset=["dias"]).reset_index())
    g["dias"] = g["dias"].astype(int)
    g["promedio_por_dia"] = g["monto"] / g["dias"]
    g["ots_por_dia"] = g["ots"] / g["dias"]
    g["lectura"] = np.where(g["dias"] < min_dias, "indicativo (pocos días)", "")
    return g


def resumen_dia_semana(por_dia: pd.DataFrame, min_dias=4) -> pd.DataFrame:
    g = (por_dia.groupby("dia_semana")
         .agg(dias=("fecha", "size"), monto=("monto", "sum"), ots=("ots", "sum"))
         .reindex(DIAS_SEMANA).dropna(subset=["dias"]).reset_index())
    g["dias"] = g["dias"].astype(int)
    g["promedio_por_dia"] = g["monto"] / g["dias"]
    g["ots_por_dia"] = g["ots"] / g["dias"]
    g["lectura"] = np.where(g["dias"] < min_dias, "indicativo (pocos días)", "")
    return g


def mo_vs_repuestos(incl: pd.DataFrame) -> dict | None:
    if not {"total_mo", "recamb"} <= set(incl.columns):
        return None
    mo, rep = float(incl["total_mo"].sum()), float(incl["recamb"].sum())
    dif = (incl["total_mo"] + incl["recamb"] - incl["monto_ot"]).abs() > 0.01
    return dict(mano_obra=mo, repuestos=rep, suma=mo + rep, monto_ot=float(incl["monto_ot"].sum()),
                pct_mano_obra=mo / (mo + rep) if (mo + rep) else None,
                filas_no_cuadran=int(dif.sum()))


def por_categoria(filas: pd.DataFrame, col: str, top: int | None = 10) -> pd.DataFrame:
    """Monto, N.º de OTs, participación y monto por OT por categoría. El resto se agrupa en 'Otros'."""
    cat = filas[col].astype("string").str.strip().fillna("(sin dato)").replace("", "(sin dato)")
    g = (filas.assign(_cat=cat).groupby("_cat")
         .agg(ots=("referencia", "nunique"), monto=("monto_ot", "sum"))
         .sort_values("monto", ascending=False))
    if top and len(g) > top:
        resto = g.iloc[top:]
        g = pd.concat([g.iloc[:top], pd.DataFrame({"ots": [resto["ots"].sum()], "monto": [resto["monto"].sum()]},
                                                   index=[f"Otros ({len(resto)})"])])
    total = g["monto"].sum()
    g["pct_monto"] = g["monto"] / total if total else np.nan
    g["monto_por_ot"] = (g["monto"] / g["ots"]).where(g["ots"] > 0)
    g.index.name = col
    return g.reset_index()


def por_tipo(filas_con_excluidas: pd.DataFrame) -> pd.DataFrame:
    g = (filas_con_excluidas.assign(tipo_norm=filas_con_excluidas["tipo_norm"].fillna("(sin dato)"))
         .groupby(["tipo_norm", "excluida"]).agg(ots=("referencia", "nunique"), monto=("monto_ot", "sum"))
         .reset_index().sort_values("monto", ascending=False))
    g["suma_a_meta"] = np.where(g["excluida"], "No (excluido)", "Sí")
    return g.drop(columns="excluida")


BORDES_KM = [-np.inf, 1, 10_000, 30_000, 60_000, 100_000, 200_000, np.inf]
ETIQUETAS_KM = ["≤ 1 (revisar dato)", "hasta 10 mil", "10 – 30 mil", "30 – 60 mil", "60 – 100 mil",
                "100 – 200 mil", "más de 200 mil"]


def rangos_km(incl: pd.DataFrame) -> pd.DataFrame | None:
    if "km" not in incl.columns:
        return None
    km = pd.to_numeric(incl["km"], errors="coerce")
    rango = pd.cut(km, BORDES_KM, labels=ETIQUETAS_KM).cat.add_categories("(sin dato)").fillna("(sin dato)")
    g = (incl.assign(rango=rango).groupby("rango", observed=False)
         .agg(ots=("referencia", "nunique"), monto=("monto_ot", "sum")).reset_index())
    g["monto_por_ot"] = (g["monto"] / g["ots"]).where(g["ots"] > 0)
    return g[g["ots"] > 0]


# ============================ Venta interna ============================

def preparar_venta_interna(df: pd.DataFrame, sufijos_excluidos, tipos_or_excluidos) -> pd.DataFrame:
    faltan = [c for c in COLUMNAS_VENTA if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas en los datos de venta interna: {faltan}")
    out = df.copy()
    out["fecha"] = pd.to_datetime(out["fecha_cierre_ot"]).dt.normalize()
    out["monto"] = pd.to_numeric(out["valor_neto_sin_impuestos"])
    codigo = _norm(out["codigo_parte"]).fillna("")
    out["excl_sufijo"] = codigo.str.endswith(tuple(s.upper() for s in sufijos_excluidos))
    out["tipo_or_norm"] = _norm(out["tipo_or"])
    out["excl_tipo_or"] = out["tipo_or_norm"].isin([t.upper() for t in tipos_or_excluidos])
    out["canal_norm"] = _norm(out["canal"])
    mv, mr = _norm(out["marca_vehiculo"]), _norm(out["marca_repuesto"])
    out["marca"] = mv.fillna(mr)
    out["origen_marca"] = np.where(mv.notna(), "vehículo", np.where(mr.notna(), "repuesto", "sin marca"))
    return out


def resumen_venta_interna(v: pd.DataFrame, marca: str, canales: dict, fecha_corte) -> dict:
    """Venta interna de una marca: acumulado del mes, día, serie diaria por canal y controles."""
    corte = pd.Timestamp(fecha_corte).normalize()
    inicio = corte.replace(day=1)
    de_marca = v["marca"].eq(marca.upper())
    pasa_reglas = de_marca & ~v["excl_sufijo"] & ~v["excl_tipo_or"]
    pasa = pasa_reglas & v["canal_norm"].isin(list(canales))
    en_mes = (v["fecha"] >= inicio) & (v["fecha"] <= corte)

    incl = v[pasa & en_mes].assign(canal_nombre=lambda d: d["canal_norm"].map(canales))
    dia = incl[incl["fecha"] == corte]
    nombres = list(canales.values())

    serie = (incl.pivot_table(index="fecha", columns="canal_nombre", values="monto", aggfunc="sum")
             .reindex(index=pd.date_range(inicio, corte, freq="D"), columns=nombres).fillna(0.0))
    serie.index.name = "fecha"

    acumulado = float(incl["monto"].sum())
    por_canal = incl.groupby("canal_nombre")["monto"].sum().reindex(nombres).fillna(0.0).rename("monto").reset_index()
    por_canal["pct"] = por_canal["monto"] / acumulado if acumulado else np.nan

    base_mes = v[de_marca & en_mes]
    embudo = pd.DataFrame([
        ("Líneas de la marca con cierre en el mes", len(base_mes), base_mes["monto"].sum()),
        ("Excluidas por sufijo de código de parte", int(base_mes["excl_sufijo"].sum()), base_mes.loc[base_mes["excl_sufijo"], "monto"].sum()),
        ("Excluidas por Tipo OR (sin contar las anteriores)", int((~base_mes["excl_sufijo"] & base_mes["excl_tipo_or"]).sum()),
         base_mes.loc[~base_mes["excl_sufijo"] & base_mes["excl_tipo_or"], "monto"].sum()),
        ("Excluidas por canal (sin contar las anteriores)", int((pasa_reglas & en_mes & ~pasa).sum()),
         v.loc[pasa_reglas & en_mes & ~pasa, "monto"].sum()),
        ("Incluidas", len(incl), acumulado),
    ], columns=["paso", "lineas", "monto"])

    otros_canales = (v[pasa_reglas & en_mes & ~pasa].assign(canal_norm=lambda d: d["canal_norm"].fillna("(sin dato)"))
                     .groupby("canal_norm")["monto"].agg(["size", "sum"]).rename(columns={"size": "lineas", "sum": "monto"})
                     .reset_index())
    sin_fecha = v[pasa & v["fecha"].isna()]
    return dict(
        marca=marca, inicio_mes=inicio, fecha_corte=corte,
        acumulado=acumulado, monto_dia=float(dia["monto"].sum()),
        lineas_mes=len(incl), lineas_dia=len(dia),
        documentos_mes=int(incl["documento"].nunique()) if "documento" in incl else None,
        por_canal=por_canal, serie=serie.reset_index(), embudo=embudo, otros_canales=otros_canales,
        sin_fecha_lineas=len(sin_fecha), sin_fecha_monto=float(sin_fecha["monto"].sum()),
        negativos_lineas=int((incl["monto"] < 0).sum()), negativos_monto=float(incl.loc[incl["monto"] < 0, "monto"].sum()),
        detalle=incl,
    )


def marcas_encontradas(v: pd.DataFrame) -> pd.DataFrame:
    return (v.assign(marca=v["marca"].fillna("(sin marca)"))
            .groupby(["marca", "origen_marca"])["monto"].agg(["size", "sum"])
            .rename(columns={"size": "lineas", "sum": "monto"}).reset_index().sort_values("lineas", ascending=False))
