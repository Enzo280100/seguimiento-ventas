# Contexto de los datos y del problema

> Estado: **validado con el usuario** (rondas de metodología 1–3, 2026-09-16), con evidencia de
> `data/preparados/resumen_preparacion.md` (modo prueba). Lo marcado *por verificar* se confirma en el Bloque 1.

## 1. Datos

| Aspecto | Definición |
|---|---|
| Origen | Excel exportados del sistema de una empresa del sector automotriz, en `data/originales/` |
| Actualización | El usuario reemplaza los archivos; cada archivo conserva los meses anteriores y solo agrega información nueva |
| Moneda | Soles (PEN); montos **sin IGV** (así los maneja la empresa) |
| Días | Se trabaja de lunes a sábado (evidencia: solo faltan domingos). Tipos de día: lunes–viernes, sábado, domingo/feriado |

### 1.1 `inf_fact.xlsx` — facturación por OT

| Aspecto | Valor |
|---|---|
| Hoja / encabezado | `INF. FACT` / fila 0 |
| Granularidad | **1 fila = 1 OT** (`Referencia` única en la muestra) |
| Fecha del indicador | **`F.cierre`** (fecha de cierre = facturación). `Fec.aper` solo como dato descriptivo |
| Monto | `Monto OT` (sin IGV). Evidencia: `Total factura` = 1,18 × `Monto OT` en mín. y máx. |
| Columnas útiles | `Tipo`, `Descripción` (x2), `Modelo`, `Motivo de Entrada`, `Total.MO`, `Recamb.`, `Km`, `Asesor`, `Estad` |
| Excluidas del proyecto | `Nombre`, `Placa`, `Bastidor` (datos personales/identificadores), `Cita` (acordado) |
| Volumen observado | 293 OTs cerradas del 1 al 15-sep-2026 (≈22 por día hábil); negativos: 4; ceros: 35 |

### 1.2 `inf_venta_int.xlsx` — venta interna de repuestos

| Aspecto | Valor |
|---|---|
| Hoja / encabezado | `INF. VENTA INT.` / fila 0 |
| Granularidad | **1 fila = 1 línea de repuesto** de un documento (`Documento` no es único) |
| Fecha del indicador | **`Fecha cierre OT`** (acordado). Vacía en ~45% de filas (ventas sin OT); *por verificar* que esas filas quedan fuera por `Tipo OR = "-"` |
| Monto ("valor total") | `Valor Neto sin impuestos` |
| Marca | `Marca vehículo` si tiene valor; si no, `Marca repuesto` (*por verificar con el listado de valores*) |
| Excluidas del proyecto | `Cliente`, `Serie vehículo` |
| Volumen observado | ≥2000 líneas del 1 al 16-sep-2026 (prueba limitada a 2000 filas); 60 negativos |

### 1.3 `cpu_hino.xlsx`

OTs Hino (5 filas en la muestra) cuyos montos y fechas ya están en `inf_fact`. **No alimenta ningún indicador** y no se procesa (acordado). Contiene datos personales.

## 2. Problema

Dashboard para el equipo de seguimiento de ventas y transacciones: logro vs meta a la fecha, patrones e insights. Un **selector único de fecha de corte** (calendario) gobierna todas las vistas.

### 2.1 Facturación

```
facturacion(dia) = Σ Monto OT   (inf_fact)
    donde Tipo ∉ {"4D", "4E", "4F"}
    dia = F.cierre
meta mensual = S/ 450 000 (sin IGV)
```
Visualización: medidor semicircular del acumulado del mes vs meta, con el aporte del día de corte.

### 2.2 Venta interna Toyota

```
venta_interna_toyota(dia, canal) = Σ Valor Neto sin impuestos   (inf_venta_int)
    donde marca = TOYOTA
      y   Código parte no termina en "CP", "CL", "L", "ML"   (todo lo que termina en L)
      y   Tipo OR ∉ {"4D", "-"}
      y   Canal ∈ {TG → "T. Servicio", BP → "T. B&P", NVS → "T. Accesorios"}
    dia = Fecha cierre OT
```
Visualización: barras diarias apiladas por canal.

### 2.3 Venta interna Hino

```
venta_interna_hino(dia) = Σ Valor Neto sin impuestos   (inf_venta_int)
    donde marca = HINO
      y   mismos filtros de Código parte y Tipo OR
      y   Canal = TG → "Venta interna Hino"
    dia = Fecha cierre OT
```
Visualización: barras diarias.

### 2.4 Relación entre indicadores

La venta interna **forma parte** de la facturación (63% de las OTs de `inf_fact` aparecen en `inf_venta_int`). Se muestran por separado y **nunca se suman**.

### 2.5 Ejemplo sintético de reglas de venta interna (valores inventados)

| Código parte | Tipo OR | Canal | Marca | Valor | Toyota | Hino |
|---|---|---|---|---|---|---|
| 90915-YZZD2 | 1A | TG | TOYOTA | 100 | Sí (T. Servicio) | No |
| 08880-80CP | 1A | TG | TOYOTA | 50 | No: termina en CP | No |
| ACEITE-L | 1A | BP | TOYOTA | 30 | No: termina en L | No |
| S1560-72190 | 1A | TG | HINO | 80 | No | Sí |
| S1560-72190 | 4D | TG | HINO | 70 | No | No: Tipo OR 4D |
| PZ-1234 | 2B | NVS | HINO | 40 | No | No: canal distinto de TG |

## 3. Puntos por verificar (Bloque 1)

1. Valores reales de `Tipo`, `Canal`, `Tipo OR`, `Marca vehículo`, `Marca repuesto` y de ambas `Descripción` de `inf_fact`.
2. Filas que pasan los filtros de venta interna con `Fecha cierre OT` vacía (si existen, se discute).
3. Tratamiento de `Tipo` vacío en facturación (propuesta: se incluye y se reporta).
4. `Monto OT` = `Total.MO` + `Recamb.` (solo informativo).
5. `Valor Neto sin impuestos` vs `Valor venta con impuestos` (¿idénticos?).
6. Feriados nacionales de Perú en la tabla de configuración.
