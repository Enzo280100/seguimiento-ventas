"""Figuras Plotly. Sin Streamlit, para poder probarlas por separado.

Colores (paleta de referencia validada): serie principal azul; categorías en orden fijo azul, naranja, aqua;
gris para lo que no suma a la meta. Los estados usan color + ícono + texto, nunca color solo.
"""
import plotly.graph_objects as go

AZUL = "#2a78d6"
AZUL_CLARO = "#86b6ef"   # días no seleccionados (énfasis en el día de corte)
CATEGORICOS = ["#2a78d6", "#eb6834", "#1baf7a"]
GRIS = "#a8a69f"
PISTA = "#e1e0d9"
MARCA = "#52514e"
ESTADOS = {
    "En meta": ("#0ca30c", "✅"),
    "Atención": ("#fab219", "⚠️"),
    "Atrasado": ("#d03b3b", "🔴"),
    "Sin referencia": ("#898781", "➖"),
}
FORMATO_S = "S/ %{y:,.0f}"


def soles(x, decimales=0):
    return "—" if x is None or x != x else f"S/ {x:,.{decimales}f}"   # x != x: NaN


def _miles(x):
    return f"{x / 1000:,.0f} mil" if x >= 1000 else f"{x:,.0f}"


def _layout(fig, alto=320, leyenda=False):
    fig.update_layout(height=alto, margin=dict(l=10, r=10, t=10, b=10), separators=".,",
                      showlegend=leyenda, barcornerradius=4, bargap=0.25, hovermode="closest",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    fig.update_yaxes(gridcolor="rgba(137,135,129,0.25)", zeroline=True, zerolinecolor="rgba(137,135,129,0.6)")
    fig.update_xaxes(showgrid=False)
    return fig


def medidor_facturacion(acumulado, meta, esperado):
    """Medidor semicircular: acumulado del mes vs meta, con marca del avance esperado a la fecha."""
    tope = max(meta, acumulado) * (1.05 if acumulado > meta else 1.0)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=acumulado,
        number=dict(prefix="S/ ", valueformat=",.0f", font=dict(size=40)),
        gauge=dict(
            shape="angular",
            axis=dict(range=[0, tope], tickvals=[0, meta / 2, meta], ticktext=["0", _miles(meta / 2), _miles(meta)],
                      tickcolor=MARCA),
            bar=dict(color=AZUL, thickness=0.35),
            bgcolor=PISTA, borderwidth=0,
            threshold=dict(line=dict(color=MARCA, width=4), thickness=0.9, value=esperado),
        ),
    ))
    fig.update_layout(height=280, margin=dict(l=60, r=60, t=30, b=10), separators=".,")
    return fig


def barras_diarias(fechas, valores, fecha_corte, tipos_dia, extra=None, formato=FORMATO_S, nombre="Monto"):
    """Barras por día; el día de corte resaltado. `extra`: texto adicional para el tooltip."""
    colores = [AZUL if f == fecha_corte else AZUL_CLARO for f in fechas]
    extra = extra if extra is not None else [""] * len(fechas)
    fig = go.Figure(go.Bar(
        x=fechas, y=valores, marker_color=colores, name=nombre,
        customdata=list(zip(tipos_dia, extra)),
        hovertemplate="%{x|%d/%m/%Y} · %{customdata[0]}<br>" + formato + "%{customdata[1]}<extra></extra>",
    ))
    fig.update_xaxes(tickformat="%d/%m", dtick="D1" if len(fechas) <= 16 else None)
    return _layout(fig)


def acumulado_vs_meta(serie, meta, fecha_corte):
    """Acumulado real vs acumulado esperado (meta repartida por días hábiles). Un solo eje."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=serie["fecha"], y=serie["esperado_acumulado"], name="Esperado",
                             mode="lines", line=dict(color=GRIS, width=2, dash="dash"),
                             hovertemplate="%{x|%d/%m} · esperado " + FORMATO_S + "<extra></extra>"))
    fig.add_trace(go.Scatter(x=serie["fecha"], y=serie["acumulado"], name="Real",
                             mode="lines+markers", line=dict(color=AZUL, width=2), marker=dict(size=8),
                             hovertemplate="%{x|%d/%m} · real " + FORMATO_S + "<extra></extra>"))
    fig.add_hline(y=meta, line=dict(color=MARCA, width=1), annotation_text=f"Meta {soles(meta)}",
                  annotation_position="top left")
    fig.add_vline(x=fecha_corte, line=dict(color=MARCA, width=1, dash="dot"))
    fig.update_xaxes(tickformat="%d/%m")
    return _layout(fig, leyenda=True)


def barras_apiladas(serie, columnas, fecha_corte):
    """Barras diarias apiladas por canal, colores en orden fijo."""
    fig = go.Figure()
    for i, col in enumerate(columnas):
        fig.add_trace(go.Bar(x=serie["fecha"], y=serie[col], name=col, marker_color=CATEGORICOS[i % len(CATEGORICOS)],
                             marker_line=dict(width=1, color="rgba(252,252,251,0.9)"),
                             hovertemplate="%{x|%d/%m/%Y} · " + col + "<br>" + FORMATO_S + "<extra></extra>"))
    fig.update_layout(barmode="relative")
    fig.add_vline(x=fecha_corte, line=dict(color=MARCA, width=1, dash="dot"))
    fig.update_xaxes(tickformat="%d/%m")
    return _layout(fig, leyenda=len(columnas) > 1)


def barras_horizontales(categorias, valores, colores=None, texto_extra=None, formato="S/ %{x:,.0f}"):
    """Ranking horizontal (mayor arriba)."""
    texto_extra = texto_extra if texto_extra is not None else [""] * len(categorias)
    fig = go.Figure(go.Bar(
        y=list(categorias)[::-1], x=list(valores)[::-1], orientation="h",
        marker_color=(list(colores)[::-1] if colores is not None else AZUL),
        customdata=list(texto_extra)[::-1],
        hovertemplate="%{y}<br>" + formato + "%{customdata}<extra></extra>",
    ))
    fig.update_xaxes(gridcolor="rgba(137,135,129,0.25)")
    fig.update_yaxes(showgrid=False)
    return _layout(fig, alto=max(220, 34 * len(categorias) + 40))


def barras_categoria(categorias, valores, texto_extra=None, formato=FORMATO_S):
    texto_extra = texto_extra if texto_extra is not None else [""] * len(categorias)
    fig = go.Figure(go.Bar(x=list(categorias), y=list(valores), marker_color=AZUL, customdata=list(texto_extra),
                           hovertemplate="%{x}<br>" + formato + "%{customdata}<extra></extra>"))
    return _layout(fig, alto=280)
