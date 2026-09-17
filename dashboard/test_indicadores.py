"""Prueba con datos SINTÉTICOS (inventados) y resultados calculados a mano.

Septiembre 2026: domingos 6, 13, 20, 27 y sin feriados -> 26 días hábiles (lunes a sábado).
Corte 05/09/2026 (sábado): días hábiles transcurridos 1–5 sep = 5; restantes = 21.
"""
from datetime import date
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from graficos import medidor_facturacion  # noqa: E402
from indicadores import dias_habiles, preparar_facturacion, resumen_facturacion  # noqa: E402

LAB = (0, 1, 2, 3, 4, 5)
FER = {date(2026, 10, 8): "Combate de Angamos", date(2026, 11, 1): "Todos los Santos"}
META = 450_000

SINTETICO = pd.DataFrame([
    # referencia, f_cierre,     tipo,   monto_ot
    (1, "2026-09-01", "1A", 10_000),     # incluida
    (2, "2026-09-02", "4D", 5_000),      # excluida
    (3, "2026-09-03", " 4e ", 3_000),    # excluida (espacios y minúscula)
    (4, "2026-09-05", "2B", 20_000),     # incluida, día de corte
    (5, "2026-09-05", None, 1_000),      # incluida, tipo vacío, día de corte
    (6, "2026-09-04", "1A", -500),       # incluida, negativa
    (7, "2026-08-31", "1A", 99_999),     # mes anterior: fuera
    (8, "2026-09-07", "1A", 7_777),      # después del corte: fuera
], columns=["referencia", "f_cierre", "tipo", "monto_ot"])


def resumen(df=SINTETICO, corte="2026-09-05"):
    return resumen_facturacion(preparar_facturacion(df, ("4D", "4E", "4F")), corte, META, FER, LAB)


def test_dias_habiles():
    assert len(dias_habiles("2026-09-01", "2026-09-30", FER, LAB)) == 26
    # octubre 2026: 31 días - 4 domingos (4, 11, 18, 25) - feriado jueves 8 = 26
    assert len(dias_habiles("2026-10-01", "2026-10-31", FER, LAB)) == 26


def test_resumen_calculado_a_mano():
    r = resumen()
    assert r["acumulado"] == 30_500                       # 10000 + 20000 + 1000 - 500
    assert r["monto_dia"] == 21_000 and r["ots_dia"] == 2
    assert r["aporte_dia"] == pytest.approx(21_000 / 30_500)
    assert r["pct_meta"] == pytest.approx(30_500 / 450_000)
    assert (r["habiles_mes"], r["habiles_transcurridos"], r["habiles_restantes"]) == (26, 5, 21)
    assert r["esperado"] == pytest.approx(450_000 * 5 / 26)  # 86 538,46
    assert r["pct_esperado"] == pytest.approx(30_500 / (450_000 * 5 / 26))  # 35,2%
    assert r["estado"] == "Atrasado"
    assert r["falta"] == 419_500
    assert r["necesario_por_dia"] == pytest.approx(419_500 / 21)   # 19 976,19
    assert r["promedio_por_dia_habil"] == 6_100                   # 30500 / 5
    assert r["alerta_ritmo"] is True
    assert r["ots_mes"] == 4


def test_controles():
    r = resumen()
    assert (r["excluidas_filas"], r["excluidas_monto"]) == (2, 8_000)
    assert set(r["excluidas_por_tipo"]) == {"4D", "4E"}
    assert r["tipo_vacio_filas"] == 1
    assert (r["negativos_filas"], r["negativos_monto"]) == (1, -500)
    assert r["habiles_sin_datos"] == []
    sin_dia_3 = SINTETICO[SINTETICO["referencia"] != 3]
    assert resumen(sin_dia_3)["habiles_sin_datos"] == [pd.Timestamp("2026-09-03")]


def test_estados_y_bordes():
    en_meta = pd.DataFrame([(1, "2026-09-05", "1A", 90_000)], columns=SINTETICO.columns)
    assert resumen(en_meta)["estado"] == "En meta"            # 90000 >= 86538
    atencion = pd.DataFrame([(1, "2026-09-05", "1A", 80_000)], columns=SINTETICO.columns)
    assert resumen(atencion)["estado"] == "Atención"          # 80000 / 86538 = 92,4%
    # 01/11/2026 es domingo y feriado: aún no hay días hábiles -> sin referencia
    nov = pd.DataFrame([(1, "2026-11-01", "1A", 1_000)], columns=SINTETICO.columns)
    r = resumen(nov, "2026-11-01")
    assert r["estado"] == "Sin referencia" and r["pct_esperado"] is None and not r["corte_es_habil"]


def test_columnas_faltantes():
    with pytest.raises(ValueError):
        preparar_facturacion(SINTETICO.drop(columns="tipo"), ("4D",))


def test_medidor():
    fig = medidor_facturacion(30_500, META, 86_538.46)
    g = fig.data[0]
    assert g.value == 30_500 and g.gauge.threshold.value == pytest.approx(86_538.46)
    assert g.gauge.axis.range == (0, META)


# ============================ Serie y patrones de facturación ============================
from indicadores import (por_categoria, por_tipo, preparar_venta_interna, rangos_km, resumen_tipo_dia,  # noqa: E402
                         resumen_venta_interna, serie_facturacion, tabla_por_dia, filas_periodo)


def test_serie_facturacion():
    f = preparar_facturacion(SINTETICO, ("4D", "4E", "4F"))
    s = serie_facturacion(f, "2026-09-05", META, FER, LAB).set_index("fecha")
    assert len(s) == 30                                          # todo septiembre
    assert s.loc["2026-09-01", "monto"] == 10_000
    assert s.loc["2026-09-02", "monto"] == 0                      # solo había un 4D
    assert s.loc["2026-09-05", "acumulado"] == 30_500
    assert pd.isna(s.loc["2026-09-07", "acumulado"])              # después del corte: vacío
    assert s.loc["2026-09-05", "esperado_acumulado"] == pytest.approx(450_000 * 5 / 26)
    assert s.loc["2026-09-30", "esperado_acumulado"] == pytest.approx(450_000)
    assert s.loc["2026-09-06", "tipo_dia"] == "Domingo o feriado" and s.loc["2026-09-05", "tipo_dia"] == "Sábado"


def test_patrones():
    f = preparar_facturacion(SINTETICO, ("4D", "4E", "4F"))
    incl = filas_periodo(f, "2026-09-01", "2026-09-05")
    dia = tabla_por_dia(incl, "2026-09-01", "2026-09-05", FER).set_index("fecha")
    assert dia.loc["2026-09-05", "ots"] == 2 and dia.loc["2026-09-05", "monto_por_ot"] == 10_500
    assert pd.isna(dia.loc["2026-09-02", "monto_por_ot"])          # 0 OTs: sin promedio
    td = resumen_tipo_dia(dia.reset_index()).set_index("tipo_dia")
    # lun-vie: 1–4 sep = 4 días, 10000 + 0 + 0 - 500 = 9500 ; sábado: 1 día, 21000
    assert td.loc["Lunes a viernes", "dias"] == 4 and td.loc["Lunes a viernes", "promedio_por_dia"] == 9_500 / 4
    assert td.loc["Sábado", "lectura"].startswith("indicativo")
    cat = por_categoria(incl.assign(asesor=["A", "B", "A", "B"]), "asesor", top=1)
    # incl ordenado: ref 1 (A, 10000), 4 (B, 20000), 5 (A, 1000), 6 (B, -500) -> B 19500, A 11000
    assert list(cat["asesor"]) == ["B", "Otros (1)"] and cat["monto"].tolist() == [19_500, 11_000]
    pt = por_tipo(filas_periodo(f, "2026-09-01", "2026-09-05", incluir_excluidas=True))
    assert pt.loc[pt["tipo_norm"] == "4D", "suma_a_meta"].item() == "No (excluido)"
    km = rangos_km(incl.assign(km=[1, 5_000, 250_000, None]))
    assert km.set_index("rango")["ots"].to_dict() == {"≤ 1 (revisar dato)": 1, "hasta 10 mil": 1, "más de 200 mil": 1, "(sin dato)": 1}


# ============================ Venta interna ============================
VENTA = pd.DataFrame([
    # fecha_cierre_ot, codigo_parte, tipo_or, canal, marca_vehiculo, marca_repuesto, valor, documento
    ("2026-09-01", "90915-YZZD2", "1A", "TG", "TOYOTA", "TOYOTA", 100, "D1"),   # Toyota T. Servicio
    ("2026-09-01", "08880-80CP", "1A", "TG", "TOYOTA", "TOYOTA", 50, "D1"),    # sufijo CP
    ("2026-09-02", "aceite-l ", "1A", "BP", "TOYOTA", "TOYOTA", 30, "D2"),     # termina en L (minúscula/espacio)
    ("2026-09-02", "PZ-1", "4D", "BP", "TOYOTA", "TOYOTA", 70, "D2"),          # Tipo OR 4D
    ("2026-09-03", "PZ-2", " - ", "NVS", None, "TOYOTA", 20, "D3"),            # Tipo OR '-'
    ("2026-09-03", "PZ-3", "2B", "NVS", None, "TOYOTA", 40, "D3"),             # Toyota por marca repuesto, T. Accesorios
    ("2026-09-03", "PZ-4", "2B", "MOS", "TOYOTA", "TOYOTA", 60, "D3"),         # canal no incluido
    ("2026-09-05", "PZ-5", "1A", "BP", "TOYOTA", "HINO", -10, "D4"),           # vehículo manda: Toyota B&P negativo
    ("2026-09-05", "S1560", "1A", "TG", "HINO", "HINO", 80, "D5"),             # Hino TG
    ("2026-09-05", "S1561", "1A", "NVS", "HINO", "HINO", 40, "D5"),            # Hino canal no TG
    (None, "S1562", "1A", "TG", "HINO", "HINO", 15, "D6"),                     # Hino sin fecha de cierre
    ("2026-08-31", "PZ-6", "1A", "TG", "TOYOTA", "TOYOTA", 999, "D0"),         # mes anterior
], columns=["fecha_cierre_ot", "codigo_parte", "tipo_or", "canal", "marca_vehiculo", "marca_repuesto",
            "valor_neto_sin_impuestos", "documento"])
CAN_T = {"TG": "T. Servicio", "BP": "T. B&P", "NVS": "T. Accesorios"}


def test_venta_interna_toyota():
    v = preparar_venta_interna(VENTA, ("CP", "CL", "ML", "L"), ("4D", "-"))
    r = resumen_venta_interna(v, "TOYOTA", CAN_T, "2026-09-05")
    assert r["acumulado"] == 130                                   # 100 + 40 - 10
    assert r["monto_dia"] == -10 and r["lineas_mes"] == 3 and r["documentos_mes"] == 3
    assert r["por_canal"].set_index("canal_nombre")["monto"].to_dict() == {"T. Servicio": 100, "T. B&P": -10, "T. Accesorios": 40}
    e = r["embudo"].set_index("paso")["lineas"].tolist()
    assert e == [8, 2, 2, 1, 3]                                    # 8 Toyota en sep; 2 sufijo; 2 Tipo OR; 1 canal; 3 incluidas
    assert r["serie"].set_index("fecha").loc["2026-09-02"].sum() == 0
    assert r["negativos_lineas"] == 1


def test_venta_interna_hino():
    v = preparar_venta_interna(VENTA, ("CP", "CL", "ML", "L"), ("4D", "-"))
    r = resumen_venta_interna(v, "HINO", {"TG": "Venta interna Hino"}, "2026-09-05")
    assert r["acumulado"] == 80 and r["monto_dia"] == 80
    assert (r["sin_fecha_lineas"], r["sin_fecha_monto"]) == (1, 15)
    assert r["otros_canales"].set_index("canal_norm")["monto"].to_dict() == {"NVS": 40}
