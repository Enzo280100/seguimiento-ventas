"""Reporte HTML autocontenido (un solo archivo) con las mismas vistas del dashboard para una fecha de corte.

Se abre en cualquier navegador (PC o celular) sin instalar nada ni conexión a internet: Plotly va incluido.
Uso: `python actualizar.py` (lo genera en reportes/) o botón de descarga en el dashboard.
"""
from __future__ import annotations

import html
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg  # noqa: E402
import graficos as gr  # noqa: E402
import indicadores as ind  # noqa: E402
from datos import PUBLICADO, fuente, leer_estado, leer_facturacion, leer_venta_interna  # noqa: E402

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

CSS = """
:root{color-scheme:light;--fondo:#f9f9f7;--superficie:#fcfcfb;--tinta:#0b0b0b;--tinta2:#52514e;--tenue:#898781;
--borde:rgba(11,11,11,.10);--azul:#2a78d6;--aviso:#fdf6e3}
*{box-sizing:border-box}
body{margin:0;background:var(--fondo);color:var(--tinta);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.contenedor{max-width:1200px;margin:0 auto;padding:16px}
h1{font-size:1.6rem;margin:.2rem 0}
h2{font-size:1.2rem;margin:1.6rem 0 .6rem}
h3{font-size:1rem;margin:1rem 0 .4rem}
.meta{color:var(--tinta2);font-size:.9rem}
nav.pestanas{position:sticky;top:0;z-index:5;background:var(--fondo);display:flex;gap:4px;overflow-x:auto;
border-bottom:1px solid var(--borde);margin:12px -16px 0;padding:0 16px}
nav.pestanas button{border:0;background:none;padding:10px 14px;font:inherit;color:var(--tinta2);cursor:pointer;
white-space:nowrap;border-bottom:3px solid transparent}
nav.pestanas button[aria-selected=true]{color:var(--tinta);border-bottom-color:var(--azul);font-weight:600}
.panel{display:none}.panel.activo{display:block}
.fila2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.tarjetas{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.tarjeta,.caja{background:var(--superficie);border:1px solid var(--borde);border-radius:10px;padding:12px 14px}
.tarjeta .etq{color:var(--tinta2);font-size:.85rem}
.tarjeta .val{font-size:1.5rem;font-weight:600;margin:2px 0}
.tarjeta .nota,.nota{color:var(--tenue);font-size:.82rem}
.estado{font-weight:600;margin:.3rem 0}
.aviso{background:var(--aviso);border:1px solid #f0dca8;border-radius:10px;padding:10px 14px;font-size:.9rem;margin:12px 0}
.tabla-envoltura{overflow-x:auto}
table.tabla{border-collapse:collapse;width:100%;font-size:.88rem;background:var(--superficie)}
table.tabla th{text-align:left;color:var(--tinta2);font-weight:600;border-bottom:1px solid var(--borde);padding:6px 8px}
table.tabla td{border-bottom:1px solid var(--borde);padding:6px 8px;font-variant-numeric:tabular-nums}
.grafico{background:var(--superficie);border:1px solid var(--borde);border-radius:10px;padding:6px;min-width:0;overflow:hidden}
footer{color:var(--tenue);font-size:.8rem;margin:28px 0 8px}
@media (max-width:760px){.fila2{grid-template-columns:1fr}.tarjeta .val{font-size:1.25rem}h1{font-size:1.3rem}}
"""

JS = """
document.querySelectorAll('nav.pestanas button').forEach(function(b){
  b.addEventListener('click',function(){
    document.querySelectorAll('nav.pestanas button').forEach(function(x){x.setAttribute('aria-selected','false')});
    document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('activo')});
    b.setAttribute('aria-selected','true');
    var panel=document.getElementById(b.dataset.panel); panel.classList.add('activo');
    ajustar(panel);
  });
});
function ajustar(panel){
  if(!window.Plotly){return}
  requestAnimationFrame(function(){panel.querySelectorAll('.js-plotly-plot').forEach(function(g){
    var w=g.parentElement.clientWidth-12;
    if(g.data&&g.data[0]&&g.data[0].type==='indicator'){
      var chico=w<520;
      Plotly.restyle(g,{'number.font.size':chico?24:40});
      Plotly.relayout(g,{width:w,height:chico?210:280,'margin.l':chico?62:60,'margin.r':chico?62:60});
    }else{Plotly.relayout(g,{width:w});}
  })});
}
window.addEventListener('resize',function(){document.querySelectorAll('.panel.activo').forEach(ajustar)});
window.addEventListener('load',function(){document.querySelectorAll('.panel.activo').forEach(ajustar)});
"""


def _e(x):
    return html.escape("" if x is None else str(x))


def _fecha(d):
    return "—" if d is None or pd.isna(d) else pd.Timestamp(d).strftime("%d/%m/%Y")


def _pct(x, dec=1):
    return "—" if x is None or pd.isna(x) else f"{x * 100:.{dec}f}%"


class _Figuras:
    """Incluye plotly.js una sola vez (en la primera figura)."""
    def __init__(self):
        self.primera = True

    def __call__(self, fig, titulo="", nota=""):
        h = fig.to_html(full_html=False, include_plotlyjs=self.primera, default_width="100%",
                        config={"displayModeBar": False, "responsive": True})
        self.primera = False
        cab = f"<h3>{_e(titulo)}</h3>" if titulo else ""
        pie = f'<div class="nota">{_e(nota)}</div>' if nota else ""
        return f'<div>{cab}<div class="grafico">{h}</div>{pie}</div>'


def _tarjeta(etiqueta, valor, nota=""):
    return (f'<div class="tarjeta"><div class="etq">{_e(etiqueta)}</div><div class="val">{_e(valor)}</div>'
            f'<div class="nota">{_e(nota)}</div></div>')


def _tabla(df: pd.DataFrame, titulo=""):
    cab = f"<h3>{_e(titulo)}</h3>" if titulo else ""
    return ("<div>" + cab + '<div class="tabla-envoltura">'
            + df.to_html(index=False, border=0, classes="tabla", escape=True, na_rep="—") + "</div></div>")


def _formatear(df, formatos, nombres):
    out = df.copy()
    for c, f in formatos.items():
        if c in out:
            out[c] = out[c].map(f)
    return out.rename(columns=nombres)


def construir_html(fact_raw: pd.DataFrame, venta_raw: pd.DataFrame | None, corte=None, fuentes: dict | None = None) -> str:
    soles = gr.soles
    fuentes = fuentes or {}
    fact = ind.preparar_facturacion(fact_raw, cfg.TIPOS_EXCLUIDOS_FACTURACION)
    venta = (ind.preparar_venta_interna(venta_raw, cfg.SUFIJOS_EXCLUIDOS_PARTE, cfg.TIPOS_OR_EXCLUIDOS)
             if venta_raw is not None else None)
    corte = pd.Timestamp(corte if corte is not None else fact["fecha"].max()).normalize()
    fecha_max = fact["fecha"].max()
    fig = _Figuras()

    r = ind.resumen_facturacion(fact, corte, cfg.META_FACTURACION_MENSUAL, cfg.FERIADOS, cfg.DIAS_LABORABLES,
                                cfg.UMBRAL_EN_META, cfg.UMBRAL_ATENCION, cfg.FACTOR_ALERTA_RITMO)
    serie = ind.serie_facturacion(fact, corte, cfg.META_FACTURACION_MENSUAL, cfg.FERIADOS, cfg.DIAS_LABORABLES)
    hasta = serie[serie["fecha"] <= corte]
    mes = f"{MESES[corte.month - 1]} {corte.year}"

    # ---------------- Pestaña 1 ----------------
    _, icono = gr.ESTADOS[r["estado"]]
    p1 = ['<h2>Facturación del mes vs meta</h2><div class="fila2"><div>',
          fig(gr.medidor_facturacion(r["acumulado"], r["meta"], r["esperado"])),
          f'<div class="estado">{icono} {_e(r["estado"])} · {_pct(r["pct_meta"])} de la meta de {_e(soles(r["meta"]))}</div>']
    if r["pct_esperado"] is not None:
        p1.append(f'<div class="nota">Marca gris = esperado a la fecha: {_e(soles(r["esperado"]))} '
                  f'({r["habiles_transcurridos"]} de {r["habiles_mes"]} días hábiles). '
                  f'Llevamos {_pct(r["pct_esperado"])} de lo esperado.</div>')
    p1 += ['</div><div class="tarjetas">',
           _tarjeta("Acumulado del mes", soles(r["acumulado"]), f"{r['ots_mes']} OTs · {_pct(r['pct_meta'])} de la meta"),
           _tarjeta(f"Facturación del {_fecha(corte)}", soles(r["monto_dia"]),
                    f"{r['ots_dia']} OTs · aporte al acumulado: {_pct(r['aporte_dia'])}"
                    + ("" if r["corte_es_habil"] else " · día no hábil")),
           _tarjeta("Falta para la meta", soles(r["falta"]), f"{r['habiles_restantes']} días hábiles restantes"),
           _tarjeta("Necesario por día hábil", soles(r["necesario_por_dia"]),
                    f"Promedio real: {soles(r['promedio_por_dia_habil'])}" + (" · ⚠️ ritmo insuficiente" if r["alerta_ritmo"] else "")),
           "</div></div>",
           '<div class="fila2">',
           fig(gr.barras_diarias(hasta["fecha"], hasta["monto"], corte, hasta["tipo_dia"],
                                 extra=[f" · {int(o)} OTs" for o in hasta["ots"].fillna(0)]),
               "Facturación por día", "Barra oscura = fecha de corte."),
           fig(gr.acumulado_vs_meta(serie, cfg.META_FACTURACION_MENSUAL, corte), "Acumulado real vs esperado",
               "Esperado = meta repartida por días hábiles (lunes a sábado sin feriados)."),
           "</div>",
           '<div class="aviso">ℹ️ El esperado supone facturación pareja por día hábil. Si la facturación se concentra '
           'a fin de mes, a mitad de mes puede verse <b>Atrasado</b> sin que sea un problema.</div>']

    vt = vh = None
    if venta is None:
        p1.append('<div class="aviso">Sin datos validados de venta interna.</div>')
    else:
        vt = ind.resumen_venta_interna(venta, cfg.MARCA_TOYOTA, cfg.CANALES_TOYOTA, corte)
        vh = ind.resumen_venta_interna(venta, cfg.MARCA_HINO, cfg.CANALES_HINO, corte)
        for titulo, v, nota in [("Venta interna Toyota", vt, "TG = T. Servicio · BP = T. B&P · NVS = T. Accesorios."),
                                ("Venta interna Hino", vh, "Canal TG.")]:
            p1 += [f"<h2>{_e(titulo)}</h2>", '<div class="tarjetas">',
                   _tarjeta("Acumulado del mes", soles(v["acumulado"])),
                   _tarjeta(f"Venta del {_fecha(corte)}", soles(v["monto_dia"]),
                            f"aporte: {_pct(v['monto_dia'] / v['acumulado'] if v['acumulado'] else None)}"),
                   _tarjeta("Líneas de repuesto del mes", f"{v['lineas_mes']:,}",
                            f"{v['documentos_mes']:,} documentos" if v["documentos_mes"] is not None else ""),
                   "</div>"]
            canales = list(v["por_canal"]["canal_nombre"])
            if len(canales) > 1:
                p1 += ['<div class="fila2">', fig(gr.barras_apiladas(v["serie"], canales, corte), "Venta por día y canal"),
                       _tabla(_formatear(v["por_canal"], {"monto": soles, "pct": _pct},
                                         {"canal_nombre": "Canal", "monto": "Monto", "pct": "Participación"}), "Acumulado por canal"),
                       "</div>"]
            else:
                p1.append(fig(gr.barras_diarias(v["serie"]["fecha"], v["serie"][canales[0]], corte,
                                                ind.tipo_de_dia(v["serie"]["fecha"], cfg.FERIADOS)), "Venta por día"))
            p1.append(f'<div class="nota">{_e(nota)} Valor Neto sin impuestos por Fecha cierre OT; excluye códigos que '
                      "terminan en CP, CL, L, ML y Tipo OR 4D o '-'. Forma parte de la facturación: no se suma a ella.</div>")
            if v["sin_fecha_lineas"]:
                p1.append(f'<div class="aviso">⚠️ {v["sin_fecha_lineas"]} líneas cumplen las reglas pero no tienen '
                          f'Fecha cierre OT ({_e(soles(v["sin_fecha_monto"], 2))}).</div>')

    # ---------------- Pestaña 2 ----------------
    inicio = r["inicio_mes"]
    incl = ind.filas_periodo(fact, inicio, corte)
    por_dia = ind.tabla_por_dia(incl, inicio, corte, cfg.FERIADOS)
    td = ind.resumen_tipo_dia(por_dia, cfg.MIN_DIAS_CONCLUSION)
    ds = ind.resumen_dia_semana(por_dia, cfg.MIN_DIAS_CONCLUSION)
    p2 = [f'<p class="meta">Período {_fecha(inicio)} – {_fecha(corte)} · {incl["referencia"].nunique()} OTs que suman a la meta. '
          "Vistas descriptivas: muestran qué pasó, no por qué.</p>",
          "<h2>¿Cambió el volumen o el monto por OT?</h2>", '<div class="fila2">',
          fig(gr.barras_diarias(por_dia["fecha"], por_dia["ots"], corte, por_dia["tipo_dia"], formato="%{y} OTs", nombre="OTs"),
              "N.º de OTs por día"),
          fig(gr.barras_diarias(por_dia["fecha"], por_dia["monto_por_ot"], corte, por_dia["tipo_dia"],
                                extra=[f" · {o} OTs" for o in por_dia["ots"]]), "Monto promedio por OT, por día"),
          "</div>", "<h2>¿Qué días rinden más?</h2>", '<div class="fila2">',
          _tabla(_formatear(td.drop(columns="ots"), {"monto": soles, "promedio_por_dia": soles, "ots_por_dia": lambda x: f"{x:.1f}"},
                            {"tipo_dia": "Tipo de día", "dias": "Días", "monto": "Facturación", "promedio_por_dia": "Promedio por día",
                             "ots_por_dia": "OTs por día", "lectura": "Lectura"}), "Por tipo de día"),
          fig(gr.barras_categoria(ds["dia_semana"], ds["promedio_por_dia"],
                                  texto_extra=[f" · {n} días · {o:.1f} OTs/día" for n, o in zip(ds["dias"], ds["ots_por_dia"])]),
              "Promedio por día de la semana", f"Con menos de {cfg.MIN_DIAS_CONCLUSION} días de un tipo, el resultado es indicativo."),
          "</div>", "<h2>¿De dónde viene la facturación?</h2>"]
    mr = ind.mo_vs_repuestos(incl)
    if mr:
        p2 += ['<div class="tarjetas">',
               _tarjeta("Mano de obra", soles(mr["mano_obra"]), f"{_pct(mr['pct_mano_obra'])} de MO + repuestos"),
               _tarjeta("Repuestos", soles(mr["repuestos"]),
                        f"{_pct(1 - mr['pct_mano_obra'] if mr['pct_mano_obra'] is not None else None)} de MO + repuestos"),
               _tarjeta("Monto OT", soles(mr["monto_ot"]),
                        "MO + repuestos = Monto OT" if mr["filas_no_cuadran"] == 0 else f"⚠️ {mr['filas_no_cuadran']} OTs no cuadran"),
               "</div>"]
    pt = ind.por_tipo(ind.filas_periodo(fact, inicio, corte, incluir_excluidas=True))
    km = ind.rangos_km(incl)
    p2 += ['<div class="fila2">',
           fig(gr.barras_horizontales(pt["tipo_norm"], pt["monto"],
                                      colores=[gr.GRIS if s.startswith("No") else gr.AZUL for s in pt["suma_a_meta"]],
                                      texto_extra=[f" · {o} OTs · suma a meta: {s}" for o, s in zip(pt["ots"], pt["suma_a_meta"])]),
               "Por Tipo de OT", "Gris = no suma a la meta."),
           (fig(gr.barras_categoria(km["rango"].astype(str), km["ots"], formato="%{y} OTs",
                                    texto_extra=[f" · {soles(m)} · {soles(p)} por OT" for m, p in zip(km["monto"], km["monto_por_ot"])]),
                "OTs por rango de kilometraje", "Valores ≤ 1 km suelen ser datos no registrados.")
            if km is not None and len(km) else "<div></div>"),
           "</div>", '<div class="fila2">']
    col_modelo = cfg.COL_MODELO if cfg.COL_MODELO in incl.columns else "modelo"
    for col, titulo in [(col_modelo, "Top 10 modelos por facturación"), ("motivo_de_entrada", "Top 10 motivos de entrada")]:
        if col in incl.columns:
            cat = ind.por_categoria(incl, col, top=10)
            p2.append(fig(gr.barras_horizontales(cat[col], cat["monto"], texto_extra=[
                f" · {o} OTs · {_pct(p)} · {soles(t)} por OT" for o, p, t in zip(cat["ots"], cat["pct_monto"], cat["monto_por_ot"])]), titulo))
    p2.append("</div>")
    if "asesor" in incl.columns:
        pa = ind.por_categoria(incl, "asesor", top=None)
        p2 += ["<h2>Por asesor</h2>",
               _tabla(_formatear(pa, {"monto": soles, "pct_monto": _pct, "monto_por_ot": soles},
                                 {"asesor": "Asesor", "ots": "OTs", "monto": "Facturación", "pct_monto": "Participación",
                                  "monto_por_ot": "Monto por OT"})),
               '<div class="nota">Participación en la facturación, no un ranking de desempeño.</div>']

    # ---------------- Pestaña 3 ----------------
    filas_estado = []
    for nombre, clave in [("Facturación (inf_fact)", "fact"), ("Venta interna (inf_venta_int)", "venta")]:
        f = fuentes.get(clave)
        filas_estado.append((nombre, f.get("preparado") if f else "—", _fecha(f.get("fecha_min")) if f else "—",
                             _fecha(f.get("fecha_max")) if f else "—", f.get("filas") if f else "—"))
    p3 = ["<h2>Estado de los datos</h2>",
          _tabla(pd.DataFrame(filas_estado, columns=["Fuente", "Preparado", "Desde", "Hasta", "Filas"])),
          "<h2>Controles de facturación</h2>",
          _tabla(pd.DataFrame([
              ("Período", f"{_fecha(r['inicio_mes'])} – {_fecha(corte)}"),
              ("Días hábiles del mes / transcurridos", f"{r['habiles_mes']} / {r['habiles_transcurridos']}"),
              ("Días hábiles sin datos hasta el corte", ", ".join(_fecha(x) for x in r["habiles_sin_datos"]) or "ninguno"),
              ("OTs excluidas (Tipo 4D, 4E, 4F)", f"{r['excluidas_filas']} · {soles(r['excluidas_monto'], 2)}"),
              ("OTs incluidas con Tipo vacío", r["tipo_vacio_filas"]),
              ("OTs con monto negativo (se suman)", f"{r['negativos_filas']} · {soles(r['negativos_monto'], 2)}"),
              ("OTs con monto cero", r["ceros_filas"]),
          ], columns=["Control", "Valor"]).astype(str))]
    if venta is not None:
        p3 += ["<h2>Controles de venta interna</h2>", '<div class="fila2">']
        for v in (vt, vh):
            p3.append("<div>" + _tabla(_formatear(v["embudo"], {"monto": lambda x: soles(x, 2)},
                                                  {"paso": "Paso", "lineas": "Líneas", "monto": "Monto"}),
                                       f"{v['marca'].title()}: de todas las líneas a las incluidas (mes)")
                      + f'<div class="nota">Sin Fecha cierre OT: {v["sin_fecha_lineas"]} líneas · '
                        f'negativas incluidas: {v["negativos_lineas"]}</div></div>')
        p3 += ["</div>", _tabla(_formatear(ind.marcas_encontradas(venta), {"monto": lambda x: soles(x, 2)},
                                           {"marca": "Marca", "origen_marca": "Origen", "lineas": "Líneas", "monto": "Monto"}),
                                "Marcas encontradas (vehículo si existe, si no repuesto)")]

    generado = datetime.now().strftime("%d/%m/%Y %H:%M")
    cabecera = (f"<h1>Seguimiento de ventas</h1><div class=\"meta\"><b>{_e(mes.capitalize())}</b> · período "
                f"{_fecha(r['inicio_mes'])} – {_fecha(corte)} · montos en <b>S/ sin IGV</b> · datos hasta {_fecha(fecha_max)}</div>")
    if corte == fecha_max:
        cabecera += '<div class="nota">La fecha de corte es el último día del archivo: si se exportó durante ese día, puede estar incompleto.</div>'

    return "".join([
        "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
        f"<title>Seguimiento de ventas · {_fecha(corte)}</title><style>{CSS}</style></head><body><div class=\"contenedor\">",
        cabecera,
        '<nav class="pestanas" role="tablist">'
        '<button data-panel="p1" aria-selected="true">📈 ¿Cómo vamos?</button>'
        '<button data-panel="p2" aria-selected="false">🔍 Patrones</button>'
        '<button data-panel="p3" aria-selected="false">📋 Control</button></nav>',
        '<section id="p1" class="panel activo">', *p1, "</section>",
        '<section id="p2" class="panel">', *p2, "</section>",
        '<section id="p3" class="panel">', *p3, "</section>",
        f"<footer>Generado el {generado}. Reporte estático de la fecha de corte {_fecha(corte)}. "
        "Facturación: suma de Monto OT por F. cierre sin Tipo 4D, 4E, 4F; meta mensual "
        f"{_e(soles(cfg.META_FACTURACION_MENSUAL))}.</footer>",
        f"</div><script>{JS}</script></body></html>",
    ])


def generar_reporte(publicado: Path = None, destino: Path = None, corte=None) -> Path:
    """Genera el HTML desde data/publicado/. Devuelve la ruta del archivo."""
    publicado = Path(publicado or PUBLICADO)
    estado = leer_estado(publicado)
    ff, fv = fuente(estado, "inf_fact.xlsx", publicado), fuente(estado, "inf_venta_int.xlsx", publicado)
    if ff is None:
        raise ValueError("No hay datos de facturación publicados. Ejecuta primero la preparación (python actualizar.py).")
    fact = leer_facturacion(ff["ruta"])
    venta = leer_venta_interna(fv["ruta"]) if fv else None
    corte = pd.Timestamp(corte if corte is not None else fact["f_cierre"].max()).normalize()
    contenido = construir_html(fact, venta, corte, dict(fact=ff, venta=fv))
    destino = Path(destino or publicado.parent.parent / "reportes" / f"reporte_ventas_hasta_{corte:%Y%m%d}.html")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")
    return destino
