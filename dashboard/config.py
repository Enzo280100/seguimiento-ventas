"""Parámetros acordados en PLAN.md / CONTEXTO.md. Editar aquí, no en el código de cálculo."""
from datetime import date

# --- Facturación (inf_fact) ---
META_FACTURACION_MENSUAL = 450_000          # S/ sin IGV
TIPOS_EXCLUIDOS_FACTURACION = ("4D", "4E", "4F")

# --- Venta interna (inf_venta_int) ---
SUFIJOS_EXCLUIDOS_PARTE = ("CP", "CL", "ML", "L")   # todo lo que termina en L queda excluido
TIPOS_OR_EXCLUIDOS = ("4D", "-")
CANALES_TOYOTA = {"TG": "T. Servicio", "BP": "T. B&P", "NVS": "T. Accesorios"}
CANALES_HINO = {"TG": "Venta interna Hino"}
MARCA_TOYOTA = "TOYOTA"
MARCA_HINO = "HINO"

# --- Patrones ---
COL_MODELO = "descripcion_1"      # "Descripción" que sigue a "Modelo" en inf_fact; si no existe se usa "modelo"
MIN_DIAS_CONCLUSION = 4           # con menos días de un tipo, el resultado se marca "indicativo"

# --- Semáforo del avance vs esperado ---
UMBRAL_EN_META = 1.00       # >= 100% del esperado a la fecha
UMBRAL_ATENCION = 0.90      # 90–99%; por debajo: atrasado
FACTOR_ALERTA_RITMO = 1.2   # alerta si lo necesario por día hábil supera 1,2 × el promedio real

# --- Calendario ---
DIAS_LABORABLES = (0, 1, 2, 3, 4, 5)   # lunes (0) a sábado (5)

# Feriados nacionales de Perú 2026. VERIFICAR con el calendario oficial y agregar días no laborables
# o feriados propios de la empresa. Formato: date(año, mes, día): "nombre".
FERIADOS = {
    date(2026, 1, 1): "Año Nuevo",
    date(2026, 4, 2): "Jueves Santo",
    date(2026, 4, 3): "Viernes Santo",
    date(2026, 5, 1): "Día del Trabajo",
    date(2026, 6, 7): "Batalla de Arica y Día de la Bandera",
    date(2026, 6, 29): "San Pedro y San Pablo",
    date(2026, 7, 23): "Día de la Fuerza Aérea del Perú",
    date(2026, 7, 28): "Fiestas Patrias",
    date(2026, 7, 29): "Fiestas Patrias",
    date(2026, 8, 6): "Batalla de Junín",
    date(2026, 8, 30): "Santa Rosa de Lima",
    date(2026, 10, 8): "Combate de Angamos",
    date(2026, 11, 1): "Día de Todos los Santos",
    date(2026, 12, 8): "Inmaculada Concepción",
    date(2026, 12, 9): "Batalla de Ayacucho",
    date(2026, 12, 25): "Navidad",
}
