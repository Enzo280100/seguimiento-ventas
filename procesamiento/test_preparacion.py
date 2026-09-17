"""Pruebas de la preparación automática con Excel SINTÉTICOS (valores inventados, mismos encabezados que los reales)."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_PROYECTO))
sys.path.insert(0, str(RAIZ_PROYECTO / "dashboard"))
from procesamiento import preparacion  # noqa: E402

CAB_FACT = ["Fec.aper", "Ingreso", "Referencia", "Tipo", "Descripción", "Taller", "Nombre", "Motivo de Entrada", "Bastidor",
            "Modelo", "Descripción", "Version", "F.cierre", "Estad", "Total.MO", "Recamb.", "Monto OT", "Imp. Anticipo",
            "Monto", "Total factura", "Placa", "Km", "Cita", "Tiem.fact", "Asesor"]
CAB_VENTA = ["Referencia", "Origen", "Canal", "Almacén", "Nombre almacén", "Código parte", "Descripción", "Cantidad",
             "Costo UN", "CostO total", "PVP UN", "PVP Total", "Valor Neto sin impuestos", "Valor venta con impuestos",
             "Beneficio", "Descuento (%)", "Moneda documento", "Tipo de cambio", "Marca repuesto",
             "Familia aprovisionamiento", "Cliente", "Tipo venta", "Tipo OR", "Estado OT", "Fecha salida",
             "Fecha apertura OT", "Fecha documento", "Fecha cierre OT", "Motivo entrada", "Documento",
             "Tipo documento venta", "Tipo de cliente", "Taller", "Nombre taller", "Marca vehículo", "Modelo vehículo",
             "Serie vehículo", "Tipo avería", "Asesor"]


def escribir_excels(raiz: Path, hasta="2026-09-05", cambio_monto=None, texto_en_monto=False):
    dest = raiz / "data" / "originales"
    dest.mkdir(parents=True, exist_ok=True)
    dias = [d for d in pd.date_range("2026-09-01", hasta) if d.dayofweek != 6]

    wb = Workbook(); ws = wb.active; ws.title = "INF. FACT"; ws.append(CAB_FACT)
    ref = 1000
    for d in dias:
        for tipo in ("1A", "4D"):
            ref += 1
            monto = 1000.0 + ref
            if cambio_monto and ref == cambio_monto[0]:
                monto = cambio_monto[1]
            valor_monto = "no numérico" if (texto_en_monto and ref == 1001) else monto
            ws.append([d.to_pydatetime(), None, ref, tipo, f"TIPO {tipo}", 1, "Cliente Ficticio", "MANT", "VIN-FICTICIO",
                       "M1", "TOYOTA HILUX", 1.0, d.to_pydatetime(), "F", 100.0, monto - 100.0, valor_monto, 0.0, monto,
                       round(monto * 1.18, 2), "ABC-123", 5000, None, 1.0, "ASESOR X"])
    wb.save(dest / "inf_fact.xlsx")

    wb = Workbook(); ws = wb.active; ws.title = "INF. VENTA INT."; ws.append(CAB_VENTA)
    for i, d in enumerate(dias):
        for canal, marca in (("TG", "TOYOTA"), ("TG", "HINO")):
            ws.append([1001 + i, "TALLER", canal, 1, "ALM", f"PZ-{i}", "REPUESTO", 1, 1.0, 1.0, 1.0, 50.0, 40.0, 40.0, 0.0,
                       0.0, "PEN", 1.0, marca, "FAM", "Cliente Ficticio", "INTERNA", "1A", "C", d.to_pydatetime(),
                       d.to_pydatetime(), d.to_pydatetime(), d.to_pydatetime(), "MANT", f"D{i}", "NV", None, 1, "T1",
                       marca, "M", "VIN-FICTICIO", None, "ASESOR Y"])
    wb.save(dest / "inf_venta_int.xlsx")


def leer_pub(raiz, nombre):
    return pd.read_csv(raiz / "data" / "publicado" / nombre, encoding="utf-8-sig")


HOY = "2026-09-30"


def test_primera_ejecucion_publica_sin_datos_personales(tmp_path):
    escribir_excels(tmp_path)
    res = preparacion.preparar(tmp_path, hoy=HOY)
    assert {r["estado"] for r in res.values()} == {"COMPLETO"}
    fact = leer_pub(tmp_path, "facturacion.csv")
    assert len(fact) == 10 and fact["referencia"].tolist()[:2] == [1001, 1002]      # 5 días x 2 OTs; enteros sin ".0"
    columnas = set(fact.columns) | set(leer_pub(tmp_path, "venta_interna.csv").columns)
    assert not columnas & {"nombre", "placa", "bastidor", "cita", "cliente", "serie_vehiculo"}
    estado = json.loads((tmp_path / "data/publicado/estado.json").read_text(encoding="utf-8"))
    assert estado["archivos"]["inf_fact.xlsx"]["datos_publicados"]["fecha_max"] == "2026-09-05"
    assert (tmp_path / "data/preparados/inf_fact_hasta_20260905.csv").exists()
    texto = (tmp_path / "data/publicado/facturacion.csv").read_text(encoding="utf-8-sig")
    assert "Cliente Ficticio" not in texto and "ABC-123" not in texto


def test_sin_cambios_no_reprocesa(tmp_path):
    escribir_excels(tmp_path)
    preparacion.preparar(tmp_path, hoy=HOY)
    lineas = (tmp_path / "data/preparados/registro_preparacion.jsonl").read_text(encoding="utf-8").count("\n")
    res = preparacion.preparar(tmp_path, hoy=HOY)
    assert not any(r["reprocesado"] for r in res.values())
    assert (tmp_path / "data/preparados/registro_preparacion.jsonl").read_text(encoding="utf-8").count("\n") == lineas


def test_agregar_dias_actualiza(tmp_path):
    escribir_excels(tmp_path, hasta="2026-09-05")
    preparacion.preparar(tmp_path, hoy=HOY)
    escribir_excels(tmp_path, hasta="2026-09-08")            # agrega 7 y 8 (6 es domingo)
    res = preparacion.preparar(tmp_path, hoy=HOY)
    assert res["inf_fact.xlsx"]["estado"] == "COMPLETO" and res["inf_fact.xlsx"]["reprocesado"]
    assert len(leer_pub(tmp_path, "facturacion.csv")) == 14


def test_historia_modificada_no_publica_y_se_puede_aceptar(tmp_path):
    escribir_excels(tmp_path, hasta="2026-09-05")
    preparacion.preparar(tmp_path, hoy=HOY)
    antes = leer_pub(tmp_path, "facturacion.csv")
    escribir_excels(tmp_path, hasta="2026-09-08", cambio_monto=(1003, 9999.0))   # cambia una OT del 02/09
    res = preparacion.preparar(tmp_path, hoy=HOY)
    assert res["inf_fact.xlsx"]["estado"] == "PARCIAL"
    assert "historia: mismos valores hasta la fecha anterior" in res["inf_fact.xlsx"]["validaciones_fallidas"]
    pd.testing.assert_frame_equal(leer_pub(tmp_path, "facturacion.csv"), antes)     # sigue lo último válido
    estado = json.loads((tmp_path / "data/publicado/estado.json").read_text(encoding="utf-8"))
    assert estado["archivos"]["inf_fact.xlsx"]["ultimo_intento"]["estado"] == "PARCIAL"
    assert preparacion.preparar(tmp_path, hoy=HOY)["inf_fact.xlsx"]["reprocesado"] is False   # no insiste
    res = preparacion.preparar(tmp_path, aceptar_cambios_historia=True, hoy=HOY)
    assert res["inf_fact.xlsx"]["estado"] == "COMPLETO"
    assert len(leer_pub(tmp_path, "facturacion.csv")) == 14


def test_valor_no_convertible_no_publica(tmp_path):
    escribir_excels(tmp_path, texto_en_monto=True)
    res = preparacion.preparar(tmp_path, hoy=HOY)
    assert res["inf_fact.xlsx"]["estado"] == "PARCIAL"
    assert "conversiones de tipo sin pérdida" in res["inf_fact.xlsx"]["validaciones_fallidas"]
    assert not (tmp_path / "data/publicado/facturacion.csv").exists()
    assert res["inf_venta_int.xlsx"]["estado"] == "COMPLETO"


def test_fechas_futuras_no_publica(tmp_path):
    escribir_excels(tmp_path, hasta="2026-09-05")
    res = preparacion.preparar(tmp_path, hoy="2026-09-03")
    assert "fechas en rango plausible" in res["inf_fact.xlsx"]["validaciones_fallidas"]


def test_reporte_html(tmp_path):
    from reporte_html import generar_reporte
    escribir_excels(tmp_path)
    preparacion.preparar(tmp_path, hoy=HOY)
    ruta = generar_reporte(tmp_path / "data" / "publicado")
    assert ruta.name == "reporte_ventas_hasta_20260905.html"
    texto = ruta.read_text(encoding="utf-8")
    assert "Seguimiento de ventas" in texto and "Venta interna Toyota" in texto and "Venta interna Hino" in texto
    assert texto.count('class="plotly-graph-div"') >= 12
    assert texto.count("plotly.js v") == 1                    # plotly incluido una sola vez (funciona sin internet)
    assert "Cliente Ficticio" not in texto
    # facturación: 5 días x OT tipo 1A (refs impares 1001..1009) = 5*1000 + (1001+1003+1005+1007+1009) = 10025
    assert "S/ 10,025" in texto
