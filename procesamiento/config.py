"""Configuración acordada (PLAN.md / CONTEXTO.md) para preparar y publicar los datos.

- fechas / numeros / textos: columnas a leer (nombres normalizados) y su tipo esperado. Si falta alguna, o algún
  valor no se puede convertir, el archivo queda PARCIAL y no se publica.
- columnas_publicadas: lo único que llega a data/publicado/ (y al repositorio). Sin datos personales.
"""

VERSION = 2   # versión del proceso; las validaciones incrementales solo comparan con ejecuciones de la misma versión

ARCHIVOS = {
    "inf_fact.xlsx": dict(
        indicador="inf_fact", hoja="INF. FACT", fila_encabezado=0,
        col_fecha="f_cierre", clave=["referencia"],
        fechas=["fec_aper", "ingreso", "f_cierre"],
        numeros=["referencia", "taller", "version", "total_mo", "recamb", "monto_ot", "imp_anticipo", "monto",
                 "total_factura", "km", "tiem_fact"],
        textos=["tipo", "descripcion", "motivo_de_entrada", "modelo", "descripcion_1", "estad", "asesor"],
        publicar="facturacion.csv",
        columnas_publicadas=["referencia", "f_cierre", "fec_aper", "tipo", "descripcion", "descripcion_1", "modelo",
                             "motivo_de_entrada", "asesor", "total_mo", "recamb", "monto_ot", "km"],
    ),
    "inf_venta_int.xlsx": dict(
        indicador="inf_venta_int", hoja="INF. VENTA INT.", fila_encabezado=0,
        col_fecha="fecha_documento", clave=[],   # nivel línea: sin clave única (acordado)
        fechas=["fecha_salida", "fecha_apertura_ot", "fecha_documento", "fecha_cierre_ot"],
        numeros=["referencia", "almacen", "cantidad", "costo_total", "pvp_total", "valor_neto_sin_impuestos",
                 "valor_venta_con_impuestos", "descuento", "taller"],
        textos=["origen", "canal", "nombre_almacen", "codigo_parte", "descripcion", "moneda_documento", "marca_repuesto",
                "familia_aprovisionamiento", "tipo_venta", "tipo_or", "estado_ot", "motivo_entrada", "documento",
                "tipo_documento_venta", "nombre_taller", "marca_vehiculo", "modelo_vehiculo", "asesor"],
        publicar="venta_interna.csv",
        columnas_publicadas=["documento", "fecha_documento", "fecha_cierre_ot", "codigo_parte", "descripcion", "canal",
                             "tipo_or", "marca_vehiculo", "marca_repuesto", "valor_neto_sin_impuestos"],
    ),
}
# cpu_hino.xlsx: fuera del proyecto (acordado).
