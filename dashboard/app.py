"""Dashboard de seguimiento de ventas y facturación.

Ejecutar desde la raíz del proyecto:  streamlit run dashboard/app.py
- Local: si hay Excel en data/originales/ y cambiaron, los prepara y publica automáticamente antes de mostrar.
- Nube (Streamlit Community Cloud): solo lee data/publicado/ del repositorio.
Definiciones: CONTEXTO.md · Metodología y controles: PLAN.md · Parámetros: dashboard/config.py y procesamiento/config.py
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parent.parent))
import config as cfg  # noqa: E402
import graficos as gr  # noqa: E402
import indicadores as ind  # noqa: E402
from datos import PUBLICADO, RAIZ, fuente, leer_estado, leer_facturacion, leer_venta_interna  # noqa: E402
from procesamiento import preparacion  # noqa: E402
from reporte_html import construir_html  # noqa: E402

soles = gr.soles
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
GRAFICO = dict(use_container_width=True, config={"displayModeBar": False})


def fecha_txt(d):
    return "—" if d is None or pd.isna(d) else pd.Timestamp(d).strftime("%d/%m/%Y")


def pct(x, dec=1):
    return "—" if x is None or pd.isna(x) else f"{x * 100:.{dec}f}%"


def tabla(df, formatos):
    """Formatea columnas para mostrar (sin alterar los datos de cálculo)."""
    out = df.copy()
    for col, fmt in formatos.items():
        if col in out:
            out[col] = out[col].map(fmt)
    return out


@st.cache_data(show_spinner=False)
def cargar_facturacion(ruta: str, _mtime: float):
    return ind.preparar_facturacion(leer_facturacion(Path(ruta)), cfg.TIPOS_EXCLUIDOS_FACTURACION)


@st.cache_data(show_spinner=False)
def cargar_venta(ruta: str, _mtime: float):
    return ind.preparar_venta_interna(leer_venta_interna(Path(ruta)), cfg.SUFIJOS_EXCLUIDOS_PARTE, cfg.TIPOS_OR_EXCLUIDOS)


@st.cache_data(show_spinner=False, max_entries=20)
def reporte_html(corte: str, _mtimes: tuple, _ff: dict, _fv: dict):
    fact_raw = leer_facturacion(_ff["ruta"])
    venta_raw = leer_venta_interna(_fv["ruta"]) if _fv else None
    return construir_html(fact_raw, venta_raw, corte, dict(fact=_ff, venta=_fv)).encode("utf-8")


# ============================ Actualización automática (solo local) ============================
st.set_page_config(page_title="Seguimiento de ventas", page_icon="📊", layout="wide")

modo_local = preparacion.hay_originales(RAIZ)
resultados = {}
if modo_local:
    with st.spinner("Revisando si hay datos nuevos en data/originales…"):
        resultados = preparacion.preparar(RAIZ)
    if any(x.get("reprocesado") and x.get("estado") == "COMPLETO" for x in resultados.values()):
        st.toast("Datos actualizados desde los Excel nuevos", icon="✅")

estado = leer_estado()
fuente_f = fuente(estado, "inf_fact.xlsx")
fuente_v = fuente(estado, "inf_venta_int.xlsx")
if fuente_f is None:
    st.title("Seguimiento de ventas")
    st.error("No hay datos de facturación publicados. Coloca los Excel en `data/originales/` y ejecuta "
             "`python actualizar.py` (o abre la app localmente).")
    for x in resultados.values():
        if x.get("estado") != "COMPLETO":
            st.warning(f"{x['archivo']}: {x.get('estado')} · {', '.join(x.get('validaciones_fallidas', [])) or x.get('mensaje', '')}")
    st.stop()

fact = cargar_facturacion(str(fuente_f["ruta"]), fuente_f["ruta"].stat().st_mtime)
venta = cargar_venta(str(fuente_v["ruta"]), fuente_v["ruta"].stat().st_mtime) if fuente_v else None

fecha_min, fecha_max = fact["fecha"].min().date(), fact["fecha"].max().date()

with st.sidebar:
    st.header("Filtros")
    corte_d = st.date_input("📅 Fecha de corte", value=fecha_max, min_value=fecha_min, max_value=fecha_max,
                            format="DD/MM/YYYY",
                            help="Todas las vistas muestran el mes de esta fecha, desde el día 1 hasta el corte.")
    alcance = st.radio("Período para Patrones", ["Mes de la fecha de corte", "Todo lo disponible hasta el corte"],
                       help="Más días dan patrones más confiables.")
    st.divider()
    st.caption(f"Facturación: {fecha_txt(fecha_min)} – {fecha_txt(fecha_max)}")
    if venta is not None and venta["fecha"].notna().any():
        st.caption(f"Venta interna (cierre OT): {fecha_txt(venta['fecha'].min())} – {fecha_txt(venta['fecha'].max())}")
    st.caption(f"Montos en S/ sin IGV · datos preparados: {fuente_f['preparado'].replace('T', ' ')}")

    # Avisos del último intento de actualización (local o publicado)
    for nombre, f in [("Facturación", fuente_f), ("Venta interna", fuente_v)]:
        intento = (f or {}).get("ultimo_intento") or {}
        if intento and intento.get("estado") != "COMPLETO":
            st.warning(f"{nombre}: la última actualización ({intento['momento'].replace('T', ' ')}) no pasó las "
                       f"validaciones ({', '.join(intento.get('validaciones_fallidas', [])) or intento.get('mensaje', '')}). "
                       "Se muestran los últimos datos válidos.")

    st.divider()
    mtimes = tuple(p.stat().st_mtime for p in PUBLICADO.glob("*.csv"))
    st.download_button("⬇️ Descargar reporte HTML", data=reporte_html(str(pd.Timestamp(corte_d).date()), mtimes, fuente_f, fuente_v),
                       file_name=f"reporte_ventas_hasta_{pd.Timestamp(corte_d):%Y%m%d}.html", mime="text/html",
                       help="Un archivo para compartir por WhatsApp o correo; se abre en el navegador sin instalar nada.")
    if modo_local:
        if st.button("🔄 Reprocesar datos", help="Vuelve a preparar los Excel aunque no hayan cambiado."):
            preparacion.preparar(RAIZ, forzar=True)
            st.cache_data.clear()
            st.rerun()
        if any("historia" in " ".join(x.get("validaciones_fallidas", [])) for x in resultados.values()):
            st.error("Los Excel nuevos cambiaron días ya reportados. Si el cambio es correcto (p. ej. una OT corregida), acéptalo:")
            if st.button("Aceptar cambios en la historia"):
                preparacion.preparar(RAIZ, aceptar_cambios_historia=True)
                st.cache_data.clear()
                st.rerun()

corte = pd.Timestamp(corte_d)
r = ind.resumen_facturacion(fact, corte, cfg.META_FACTURACION_MENSUAL, cfg.FERIADOS, cfg.DIAS_LABORABLES,
                            cfg.UMBRAL_EN_META, cfg.UMBRAL_ATENCION, cfg.FACTOR_ALERTA_RITMO)
nombre_mes = f"{MESES[r['inicio_mes'].month - 1]} {r['inicio_mes'].year}"
serie = ind.serie_facturacion(fact, corte, cfg.META_FACTURACION_MENSUAL, cfg.FERIADOS, cfg.DIAS_LABORABLES)
serie_hasta = serie[serie["fecha"] <= corte]

vt = vh = None
if venta is not None:
    vt = ind.resumen_venta_interna(venta, cfg.MARCA_TOYOTA, cfg.CANALES_TOYOTA, corte)
    vh = ind.resumen_venta_interna(venta, cfg.MARCA_HINO, cfg.CANALES_HINO, corte)

st.title("Seguimiento de ventas")
st.caption(f"**{nombre_mes.capitalize()}** · período {fecha_txt(r['inicio_mes'])} – {fecha_txt(corte)} · "
           f"montos en **S/ sin IGV** · actualizado con datos hasta {fecha_txt(fecha_max)}")
if corte.date() == fecha_max:
    st.caption("ℹ️ La fecha de corte es el último día del archivo: si se exportó durante ese día, puede estar incompleto.")

tab_como, tab_patrones, tab_detalle = st.tabs(["📈 ¿Cómo vamos?", "🔍 Patrones", "📋 Detalle y control"])

# ============================ Pestaña 1: ¿Cómo vamos? ============================
with tab_como:
    st.subheader("Facturación del mes vs meta")
    col_medidor, col_tarjetas = st.columns([1.1, 1])
    with col_medidor:
        st.plotly_chart(gr.medidor_facturacion(r["acumulado"], r["meta"], r["esperado"]), **GRAFICO)
        _, icono = gr.ESTADOS[r["estado"]]
        st.markdown(f"**{icono} {r['estado']}** · {pct(r['pct_meta'])} de la meta de {soles(r['meta'])}")
        if r["pct_esperado"] is not None:
            st.caption(f"La marca gris es lo esperado a hoy: {soles(r['esperado'])} "
                       f"({r['habiles_transcurridos']} de {r['habiles_mes']} días hábiles). "
                       f"Llevamos {pct(r['pct_esperado'])} de lo esperado.")
    with col_tarjetas:
        a, b = st.columns(2)
        a.metric("Acumulado del mes", soles(r["acumulado"]),
                 help="Suma de Monto OT (F. cierre en el mes, hasta el corte), sin Tipo 4D, 4E, 4F.")
        a.caption(f"{r['ots_mes']} OTs · {pct(r['pct_meta'])} de la meta")
        b.metric(f"Facturación del {fecha_txt(corte)}", soles(r["monto_dia"]))
        b.caption(f"{r['ots_dia']} OTs · aporte al acumulado: {pct(r['aporte_dia'])}"
                  + ("" if r["corte_es_habil"] else " · día no hábil"))
        c, d = st.columns(2)
        c.metric("Falta para la meta", soles(r["falta"]))
        c.caption(f"{r['habiles_restantes']} días hábiles restantes")
        d.metric("Necesario por día hábil", soles(r["necesario_por_dia"]))
        d.caption(f"Promedio real: {soles(r['promedio_por_dia_habil'])} por día hábil"
                  + (" · ⚠️ ritmo insuficiente" if r["alerta_ritmo"] else ""))

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Facturación por día**")
        st.plotly_chart(gr.barras_diarias(
            serie_hasta["fecha"], serie_hasta["monto"], corte, serie_hasta["tipo_dia"],
            extra=[f" · {int(o)} OTs" for o in serie_hasta["ots"].fillna(0)]), **GRAFICO)
        st.caption("Barra oscura = fecha de corte. Pasa el cursor para ver tipo de día y N.º de OTs.")
    with g2:
        st.markdown("**Acumulado real vs esperado**")
        st.plotly_chart(gr.acumulado_vs_meta(serie, cfg.META_FACTURACION_MENSUAL, corte), **GRAFICO)
        st.caption("Esperado = meta repartida por días hábiles (lunes a sábado sin feriados).")

    st.info("El esperado supone facturación pareja por día hábil. Si la facturación se concentra a fin de mes, "
            "a mitad de mes puede verse **Atrasado** sin que sea un problema. Sin meses anteriores todavía no hay "
            "referencia histórica.", icon="ℹ️")

    st.divider()
    for titulo, v, nota in [
        ("Venta interna Toyota", vt, "Canales: TG = T. Servicio · BP = T. B&P · NVS = T. Accesorios."),
        ("Venta interna Hino", vh, "Canal TG."),
    ]:
        st.subheader(titulo)
        if v is None:
            st.warning("No hay datos validados de `inf_venta_int.xlsx` (estado COMPLETO). Ejecuta el notebook en modo completo.")
            continue
        m1, m2, m3 = st.columns(3)
        m1.metric("Acumulado del mes", soles(v["acumulado"]))
        m2.metric(f"Venta del {fecha_txt(corte)}", soles(v["monto_dia"]))
        m2.caption(f"aporte al acumulado: {pct(v['monto_dia'] / v['acumulado'] if v['acumulado'] else None)}")
        m3.metric("Líneas de repuesto del mes", f"{v['lineas_mes']:,}")
        if v["documentos_mes"] is not None:
            m3.caption(f"{v['documentos_mes']:,} documentos")
        canales = list(v["por_canal"]["canal_nombre"])
        if len(canales) > 1:
            gc, tc = st.columns([2, 1])
            with gc:
                st.plotly_chart(gr.barras_apiladas(v["serie"], canales, corte), **GRAFICO)
            with tc:
                st.markdown("**Acumulado por canal**")
                st.dataframe(tabla(v["por_canal"].rename(columns={"canal_nombre": "Canal", "monto": "Monto", "pct": "Participación"}),
                                   {"Monto": lambda x: soles(x), "Participación": pct}),
                             hide_index=True, use_container_width=True)
        else:
            st.plotly_chart(gr.barras_diarias(v["serie"]["fecha"], v["serie"][canales[0]], corte,
                                              ind.tipo_de_dia(v["serie"]["fecha"], cfg.FERIADOS)), **GRAFICO)
        st.caption(f"{nota} Suma de Valor Neto sin impuestos por Fecha cierre OT; excluye códigos que terminan en "
                   "CP, CL, L, ML y Tipo OR 4D o '-'. Forma parte de la facturación: no se suma a ella.")
        if v["sin_fecha_lineas"]:
            st.warning(f"{v['sin_fecha_lineas']} líneas cumplen las reglas pero no tienen Fecha cierre OT "
                       f"({soles(v['sin_fecha_monto'], 2)}); no aparecen en ningún día. Ver Detalle y control.")

# ============================ Pestaña 2: Patrones ============================
with tab_patrones:
    inicio_p = r["inicio_mes"] if alcance.startswith("Mes") else fact["fecha"].min()
    incl_p = ind.filas_periodo(fact, inicio_p, corte)
    todas_p = ind.filas_periodo(fact, inicio_p, corte, incluir_excluidas=True)
    por_dia = ind.tabla_por_dia(incl_p, inicio_p, corte, cfg.FERIADOS)
    st.caption(f"Período: {fecha_txt(inicio_p)} – {fecha_txt(corte)} · {len(por_dia)} días calendario · "
               f"{incl_p['referencia'].nunique()} OTs que suman a la meta · facturación (Monto OT, S/ sin IGV). "
               "Vistas descriptivas: muestran qué pasó, no por qué.")

    st.subheader("¿Cambió el volumen o el monto por OT?")
    p1, p2 = st.columns(2)
    with p1:
        st.markdown("**N.º de OTs por día**")
        st.plotly_chart(gr.barras_diarias(por_dia["fecha"], por_dia["ots"], corte, por_dia["tipo_dia"],
                                          formato="%{y} OTs", nombre="OTs"), **GRAFICO)
    with p2:
        st.markdown("**Monto promedio por OT, por día**")
        st.plotly_chart(gr.barras_diarias(por_dia["fecha"], por_dia["monto_por_ot"], corte, por_dia["tipo_dia"],
                                          extra=[f" · {o} OTs" for o in por_dia["ots"]]), **GRAFICO)
    st.caption("Si la facturación de un día baja, compara: ¿hubo menos OTs o OTs más pequeñas? "
               "Una sola OT grande puede subir mucho el promedio de un día.")

    st.subheader("¿Qué días rinden más?")
    d1, d2 = st.columns(2)
    formato_dias = {"monto": lambda x: soles(x), "promedio_por_dia": lambda x: soles(x),
                    "ots_por_dia": lambda x: f"{x:.1f}"}
    nombres_dias = {"monto": "Facturación", "promedio_por_dia": "Promedio por día", "ots_por_dia": "OTs por día",
                    "dias": "Días", "lectura": "Lectura"}
    with d1:
        st.markdown("**Por tipo de día**")
        td = ind.resumen_tipo_dia(por_dia, cfg.MIN_DIAS_CONCLUSION)
        st.dataframe(tabla(td, formato_dias).drop(columns="ots").rename(columns={"tipo_dia": "Tipo de día", **nombres_dias}),
                     hide_index=True, use_container_width=True)
    with d2:
        st.markdown("**Promedio por día de la semana**")
        ds = ind.resumen_dia_semana(por_dia, cfg.MIN_DIAS_CONCLUSION)
        st.plotly_chart(gr.barras_categoria(ds["dia_semana"], ds["promedio_por_dia"],
                                            texto_extra=[f" · {n} días · {o:.1f} OTs/día" for n, o in zip(ds["dias"], ds["ots_por_dia"])]),
                        **GRAFICO)
    st.caption(f"Con menos de {cfg.MIN_DIAS_CONCLUSION} días de un tipo, el resultado es indicativo. "
               "Los feriados cuentan como 'Domingo o feriado'.")

    st.subheader("¿De dónde viene la facturación?")
    mr = ind.mo_vs_repuestos(incl_p)
    if mr:
        x1, x2, x3 = st.columns(3)
        x1.metric("Mano de obra (Total.MO)", soles(mr["mano_obra"]))
        x1.caption(f"{pct(mr['pct_mano_obra'])} de MO + repuestos")
        x2.metric("Repuestos (Recamb.)", soles(mr["repuestos"]))
        x2.caption(f"{pct(1 - mr['pct_mano_obra'] if mr['pct_mano_obra'] is not None else None)} de MO + repuestos")
        x3.metric("Monto OT", soles(mr["monto_ot"]))
        x3.caption("✅ MO + repuestos = Monto OT en todas las OTs" if mr["filas_no_cuadran"] == 0 else
                   f"⚠️ {mr['filas_no_cuadran']} OTs donde MO + repuestos ≠ Monto OT")

    t1, t2 = st.columns(2)
    with t1:
        st.markdown("**Por Tipo de OT** (gris = no suma a la meta)")
        pt = ind.por_tipo(todas_p)
        st.plotly_chart(gr.barras_horizontales(
            pt["tipo_norm"], pt["monto"], colores=[gr.GRIS if s.startswith("No") else gr.AZUL for s in pt["suma_a_meta"]],
            texto_extra=[f" · {o} OTs · suma a meta: {s}" for o, s in zip(pt["ots"], pt["suma_a_meta"])]), **GRAFICO)
    with t2:
        st.markdown("**Por rango de kilometraje**")
        km = ind.rangos_km(incl_p)
        if km is not None and len(km):
            st.plotly_chart(gr.barras_categoria(km["rango"].astype(str), km["ots"], formato="%{y} OTs",
                                                texto_extra=[f" · {soles(m)} · {soles(p)} por OT" for m, p in zip(km["monto"], km["monto_por_ot"])]),
                            **GRAFICO)
            st.caption("N.º de OTs por kilometraje registrado. Valores ≤ 1 km suelen ser datos no registrados.")

    col_modelo = cfg.COL_MODELO if cfg.COL_MODELO in incl_p.columns else "modelo"
    r1, r2 = st.columns(2)
    for contenedor, col, titulo in [(r1, col_modelo, "Top 10 modelos por facturación"),
                                    (r2, "motivo_de_entrada", "Top 10 motivos de entrada por facturación")]:
        with contenedor:
            st.markdown(f"**{titulo}**")
            if col in incl_p.columns:
                cat = ind.por_categoria(incl_p, col, top=10)
                st.plotly_chart(gr.barras_horizontales(
                    cat[col], cat["monto"],
                    texto_extra=[f" · {o} OTs · {pct(p)} · {soles(t)} por OT" for o, p, t in zip(cat["ots"], cat["pct_monto"], cat["monto_por_ot"])]),
                    **GRAFICO)
            else:
                st.caption(f"Columna `{col}` no disponible.")

    st.subheader("Por asesor")
    if "asesor" in incl_p.columns:
        pa = ind.por_categoria(incl_p, "asesor", top=None)
        st.dataframe(tabla(pa, {"monto": lambda x: soles(x), "pct_monto": pct, "monto_por_ot": lambda x: soles(x)})
                     .rename(columns={"asesor": "Asesor", "ots": "OTs", "monto": "Facturación",
                                      "pct_monto": "Participación", "monto_por_ot": "Monto por OT"}),
                     hide_index=True, use_container_width=True)
        st.caption("Participación en la facturación del período, no un ranking de desempeño: los asesores pueden "
                   "atender tipos de OT o vehículos distintos. Con pocas OTs, el monto por OT varía mucho.")

# ============================ Pestaña 3: Detalle y control ============================
with tab_detalle:
    st.subheader("Estado de los datos")
    filas_estado = []
    for nombre, f, df_f in [("Facturación (inf_fact)", fuente_f, fact), ("Venta interna (inf_venta_int)", fuente_v, venta)]:
        intento = (f or {}).get("ultimo_intento") or {}
        filas_estado.append((nombre, f["ruta"].name if f else "sin datos publicados", f["preparado"] if f else "—",
                             fecha_txt(f["fecha_min"]) if f else "—", fecha_txt(f["fecha_max"]) if f else "—",
                             len(df_f) if df_f is not None else 0,
                             intento.get("estado", "—") + (f" ({', '.join(intento.get('validaciones_fallidas', []))})"
                                                           if intento.get("validaciones_fallidas") else "")))
    st.dataframe(pd.DataFrame(filas_estado, columns=["Fuente", "Archivo publicado", "Preparado", "Desde", "Hasta", "Filas",
                                                     "Último intento"]),
                 hide_index=True, use_container_width=True)
    st.caption("Venta interna: 'Desde/Hasta' se refiere a Fecha documento (fecha de control del archivo).")

    st.subheader("Controles de facturación")
    controles = pd.DataFrame([
        ("Período", f"{fecha_txt(r['inicio_mes'])} – {fecha_txt(corte)}"),
        ("Días hábiles del mes / transcurridos", f"{r['habiles_mes']} / {r['habiles_transcurridos']}"),
        ("Días hábiles sin datos hasta el corte", ", ".join(fecha_txt(x) for x in r["habiles_sin_datos"]) or "ninguno"),
        ("OTs excluidas (Tipo 4D, 4E, 4F)", f"{r['excluidas_filas']} · {soles(r['excluidas_monto'], 2)}"),
        ("Detalle excluidas por tipo",
         "; ".join(f"{t}: {x['size']} OTs, {soles(x['sum'], 2)}" for t, x in r["excluidas_por_tipo"].items()) or "—"),
        ("OTs incluidas con Tipo vacío", r["tipo_vacio_filas"]),
        ("OTs con monto negativo (se suman)", f"{r['negativos_filas']} · {soles(r['negativos_monto'], 2)}"),
        ("OTs con monto cero", r["ceros_filas"]),
        ("Referencias repetidas en el período", r["referencias_repetidas"]),
    ], columns=["Control", "Valor"])
    st.dataframe(controles.astype(str), hide_index=True, use_container_width=True)

    st.subheader("Controles de venta interna")
    if venta is None:
        st.warning("Sin datos validados de venta interna.")
    else:
        c1, c2 = st.columns(2)
        for contenedor, v in [(c1, vt), (c2, vh)]:
            with contenedor:
                st.markdown(f"**{v['marca'].title()}: de todas las líneas a las incluidas (mes)**")
                st.dataframe(tabla(v["embudo"], {"monto": lambda x: soles(x, 2)})
                             .rename(columns={"paso": "Paso", "lineas": "Líneas", "monto": "Monto"}),
                             hide_index=True, use_container_width=True)
                extra = [f"Líneas que cumplen reglas sin Fecha cierre OT (todo el archivo): {v['sin_fecha_lineas']} · {soles(v['sin_fecha_monto'], 2)}",
                         f"Líneas negativas incluidas (se suman): {v['negativos_lineas']} · {soles(v['negativos_monto'], 2)}"]
                if len(v["otros_canales"]):
                    extra.append("Canales no incluidos: " + "; ".join(
                        f"{c} ({n} líneas, {soles(m, 2)})" for c, n, m in v["otros_canales"].itertuples(index=False)))
                for e in extra:
                    st.caption(e)
        with st.expander("Marcas encontradas en todo el archivo (vehículo si existe, si no repuesto)"):
            st.dataframe(tabla(ind.marcas_encontradas(venta), {"monto": lambda x: soles(x, 2)}),
                         hide_index=True, use_container_width=True)

    st.subheader("Detalle de OTs del mes")
    columnas_ot = [c for c in ["referencia", "f_cierre", "fec_aper", "tipo", "descripcion", cfg.COL_MODELO,
                               "motivo_de_entrada", "asesor", "total_mo", "recamb", "monto_ot", "km", "excluida"]
                   if c in fact.columns]
    detalle_ot = ind.filas_periodo(fact, r["inicio_mes"], corte, incluir_excluidas=True)[columnas_ot]
    detalle_ot = detalle_ot.rename(columns={"excluida": "no_suma_a_meta"}).sort_values("f_cierre", ascending=False)
    st.dataframe(detalle_ot, hide_index=True, use_container_width=True, height=360)
    st.download_button("⬇️ Descargar OTs del mes (CSV)", detalle_ot.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"ots_{r['inicio_mes']:%Y%m}_hasta_{corte:%Y%m%d}.csv", mime="text/csv")

    if venta is not None:
        st.subheader("Detalle de venta interna incluida del mes")
        cols_v = [c for c in ["fecha_cierre_ot", "documento", "codigo_parte", "descripcion", "canal", "canal_nombre",
                              "tipo_or", "marca", "origen_marca", "valor_neto_sin_impuestos"]]
        det_v = pd.concat([vt["detalle"], vh["detalle"]])
        det_v = det_v[[c for c in cols_v if c in det_v.columns]].sort_values("fecha_cierre_ot", ascending=False)
        st.dataframe(det_v, hide_index=True, use_container_width=True, height=360)
        st.download_button("⬇️ Descargar venta interna del mes (CSV)", det_v.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"venta_interna_{r['inicio_mes']:%Y%m}_hasta_{corte:%Y%m%d}.csv", mime="text/csv")
