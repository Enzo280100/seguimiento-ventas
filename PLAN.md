# Plan de trabajo

> Metodología acordada en rondas 1–3 (2026-09-16). Definiciones de datos e indicadores: `CONTEXTO.md`.

## 1. Metodología

**Enfoque:** reporte descriptivo de seguimiento, simple y legible para un equipo comercial. Sin modelos
estadísticos; comparaciones directas, siempre con período, unidades y cuántos días/OTs hay detrás.

**Herramienta:** Streamlit (Python), mismo lenguaje que la preparación. Un solo código en `dashboard/`.

**Flujo:** `data/originales/*.xlsx` → `notebooks/01_preparacion.ipynb` (valida y guarda CSV) →
`dashboard/` (lee el último CSV validado, calcula indicadores con funciones probadas y los muestra).

### 1.1 Estructura del dashboard

Un **selector único de fecha de corte** (calendario). Por defecto: última fecha con datos. Cada vista
muestra el mes de la fecha de corte hasta ese día, con el día resaltado.

| Pestaña | Contenido |
|---|---|
| 1. ¿Cómo vamos? | Medidor facturación vs meta con marca de avance esperado; tarjetas (acumulado, día y aporte, falta, necesario por día hábil); barras diarias + acumulado vs meta; Toyota apilado por canal + tabla; Hino |
| 2. Patrones | N.º de OTs y monto promedio por OT; por tipo de día y día de semana; MO vs repuestos; por `Tipo` (incluye excluidos marcados); top 10 modelos y motivos; por asesor (tabla de participación, sin semáforo) |
| 3. Detalle y control | Tabla de OTs sin datos personales; estado de los datos |

### 1.2 Monitoreo

| Indicador | Referencia | Frecuencia | Umbral |
|---|---|---|---|
| Facturación acumulada del mes | Esperado = meta × días hábiles transcurridos ÷ días hábiles del mes | En cada actualización | En meta ≥100% · Atención 90–99% · Atrasado <90% del esperado |
| Necesario por día hábil restante | Promedio real por día hábil del mes | En cada actualización | Alerta si necesario > 1,2 × promedio real |
| Venta interna Toyota / Hino | Acumulado y participación por canal | En cada actualización | Informativo (sin historia no hay base) |

Día hábil = lunes a sábado, excepto feriados de `dashboard/config.py`.

### 1.3 Criterios de interpretación

- Comparar solo períodos con el mismo número de días hábiles.
- Mostrar siempre N.º de días u OTs detrás de cada cifra; con menos de 4 días de un tipo, el patrón es "indicativo".
- Una OT grande puede mover un día: mostrar N.º de OTs junto al monto.
- Descriptivo, no causal: no atribuir causas a variaciones.
- Venta interna y facturación nunca se suman.

## 2. Controles

| Control | Dónde |
|---|---|
| Archivo validado (estado `COMPLETO`), fecha máxima por archivo | Notebook + panel del dashboard |
| Días hábiles sin datos en el mes | Dashboard |
| Filas y monto excluidos por cada regla | Dashboard |
| Negativos y ceros (conteo y monto) | Dashboard |
| Valores de categorías (`Tipo`, `Canal`, `Tipo OR`, marcas) y sufijos | Notebook (sección 7b) |
| Historia sin cambios entre actualizaciones (conteo y huella hasta la fecha máxima anterior) | Notebook |
| Último día posiblemente incompleto | Dashboard (aviso) |
| Conciliación manual de 1–2 días contra el sistema | Usuario, una vez por indicador |
| Cálculo independiente sobre caso sintético | `dashboard/test_indicadores.py` |

## 3. Limitaciones

- Solo hay datos desde sep-2026 (facturación por cierre): sin comparaciones con meses anteriores ni umbrales históricos.
- Posible concentración de facturación a fin de mes: el semáforo puede marcar "atrasado" a mitad de mes sin que sea un problema. Leer con cautela hasta tener 2–3 meses.
- Los patrones con pocos días son indicativos.
- La meta fija no considera estacionalidad.
- Regla "termina en L" amplia: puede excluir repuestos legítimos (visible en controles).

## 4. Orden de construcción

> 2026-09-16: a pedido del usuario se construyeron todos los elementos en una sola entrega (en lugar de uno por
> ronda). Queda pendiente la validación con datos reales de cada uno.

| # | Elemento | Estado |
|---|---|---|
| 1 | Preparación + indicador de facturación del mes (selector de fecha, medidor, tarjetas) | Construido · validación real pendiente |
| 2 | Barras diarias de facturación + acumulado real vs esperado | Construido · validación real pendiente |
| 3 | Venta interna Toyota (barras apiladas por canal + tabla por canal) | Construido · **reglas de marca/canal sin verificar con datos reales** |
| 4 | Venta interna Hino | Construido · **reglas de marca sin verificar con datos reales** |
| 5 | Patrones: OTs y monto por OT por día; tipo de día y día de semana; MO vs repuestos; por Tipo; km; top modelos y motivos; asesor | Construido · validación real pendiente |
| 6 | Detalle y control: estado de datos, controles de facturación y venta interna (embudo por regla, sin fecha, canales y marcas no incluidas), detalle descargable | Construido · validación real pendiente |
| 7 | Compartir con el equipo: Streamlit Community Cloud (repo público) + reporte HTML | Construido · despliegue pendiente (usuario) |
| Fase 2 | Comparación con meses anteriores; semáforo de venta interna | Con 2–3 meses de historia |

### Verificación realizada (datos sintéticos, 2026-09-16)

| Verificación | Resultado |
|---|---|
| `pytest dashboard`: 10 pruebas con resultados calculados a mano (facturación, serie, patrones, Toyota, Hino, bordes) | ✅ Pasa |
| Excel sintético → notebook → CSV → dashboard vs cálculo independiente sobre el Excel (facturación, Toyota, Hino) | ✅ Coinciden |
| `app.py` ejecutado completo con Streamlit simulado (corte por defecto, domingo, sin venta interna, sin datos) | ✅ Sin errores; 12 figuras válidas |
| App en Streamlit real y con datos reales | ⏳ Pendiente (usuario) |

## 4b. Automatización y distribución (2026-09-16)

| Pieza | Qué hace | Verificación (sintética) |
|---|---|---|
| `procesamiento/preparacion.py` | Reemplaza la corrida manual del notebook: detecta Excel cambiados (hash), convierte tipos sin pérdida, valida (columnas, filas, fechas, clave, historia sin cambios) y publica solo si todo pasa | 7 pruebas: primera carga, sin cambios, días agregados, historia modificada (no publica; aceptable con confirmación), valor no convertible, fechas futuras, HTML |
| `data/publicado/` | CSV validados solo con columnas del dashboard (sin clientes, placas, VIN) + `estado.json`. Única fuente del dashboard, local y nube | Prueba: sin "Cliente Ficticio" ni placas en lo publicado |
| `dashboard/app.py` | Local: prepara automáticamente al abrir; botones reprocesar / aceptar cambios / descargar HTML. Nube: solo lee `data/publicado/` | Streamlit simulado en modo local y nube: sin errores, 12 figuras |
| `dashboard/reporte_html.py` | HTML autocontenido (3 pestañas, Plotly incluido, adaptable a celular) | Revisado visualmente en escritorio y 375 px (datos sintéticos) |
| `actualizar.py` / `.bat` | Prepara + HTML + `git push` de `data/publicado/` (Streamlit Cloud se redepliega solo) | CLI ejecutada; `git push` no probado (requiere repo del usuario) |
| `.gitignore` | Excluye originales, preparados, reportes, notebooks y `.xlsx` | Verificado con archivos ficticios: solo entran código y `data/publicado/` |

Decisión del usuario: repositorio **público** (acepta que facturación, venta interna, modelos y asesores sean visibles).
El notebook queda como herramienta opcional de exploración/auditoría; el flujo oficial es `procesamiento/`.

## 5. Elemento 1 — detalle

### 5.1 Qué incluye

- **Notebook:** configuración definitiva (`inf_fact`: fecha `F.cierre`, clave `Referencia`; `inf_venta_int`:
  fecha de control `Fecha documento`, sin clave única por ser nivel línea); solo columnas necesarias (sin datos
  personales); `cpu_hino` fuera; reglas acordadas (no eliminar ni imputar); sección 7b con valores de categorías
  y controles de reglas.
- **Dashboard:** `dashboard/app.py` con selector de fecha de corte, medidor de facturación vs meta con marca de
  esperado, tarjetas y panel de período, cobertura y controles.
- **Cálculos:** `dashboard/indicadores.py` (funciones sin lectura de archivos) y prueba con caso sintético
  calculado a mano en `dashboard/test_indicadores.py`.

### 5.2 Cómo se valida

1. `pytest dashboard` pasa (cálculo independiente sobre datos inventados).
2. El usuario ejecuta el notebook en modo `completo`; `inf_fact` queda `COMPLETO` y se genera el CSV.
3. El usuario revisa la sección 7b: valores de `Tipo` (¿existen 4D/4E/4F con esos textos exactos?).
4. **Conciliación:** para una fecha de corte, el usuario compara acumulado del mes y monto del día contra su
   sistema o un filtro manual en Excel (`F.cierre` del mes, sin `Tipo` 4D/4E/4F, suma de `Monto OT`). Deben coincidir.
5. Revisión de legibilidad e interpretación del medidor y las tarjetas.

### 5.3 Compartir (decisión pendiente, antes del elemento 7)

| Opción | Ventaja | Límite |
|---|---|---|
| Red local: la app corre en una PC y el equipo abre `http://<ip-pc>:8501` | Los datos no salen de la empresa; cero costo | La PC debe estar encendida; solo dentro de la red |
| Streamlit Community Cloud (app privada con correos invitados) | Acceso desde cualquier lugar | Requiere subir código y CSV a GitHub/nube: necesita autorización de la empresa |
| Servidor interno de la empresa | Siempre disponible, datos internos | Depende de TI |

Recomendación: empezar en red local; decidir nube o servidor con TI.

### 5.4 Estado de validación del elemento 1 (2026-09-16)

| Paso | Estado |
|---|---|
| Notebook: configuración acordada + sección 7b | Construido; probado con Excel sintéticos (modo prueba y completo, estado COMPLETO) |
| `pytest dashboard` (6 pruebas, casos calculados a mano) | ✅ Pasa |
| Cálculo del dashboard vs cálculo independiente sobre Excel sintético | ✅ Coinciden acumulado y día |
| `app.py` | Compila; **no ejecutado** (Streamlit no instalado en el entorno de construcción) |
| Ejecución con datos reales (notebook `completo` + app) | ⏳ Pendiente (usuario) |
| Revisión de valores reales de `Tipo` (sección 7b) | ⏳ Pendiente (usuario) |
| Conciliación de acumulado y día contra el sistema | ⏳ Pendiente (usuario) |
| Revisión de legibilidad e interpretación | ⏳ Pendiente (usuario) |

## 6. Pendientes

- **Validación con datos reales (usuario):** notebook en modo completo; revisar sección 7b; conciliar con el sistema
  1–2 días de facturación, Toyota y Hino; revisar legibilidad de cada pestaña.

- Valores reales de categorías y regla de marca (CONTEXTO §3).
- Duplicados exactos en `inf_venta_int` (3 en la muestra): se conservan hasta revisarlos (pueden ser líneas legítimas).
- Tratamiento de `Tipo` vacío en facturación (propuesta: incluir y reportar).
- Lista de feriados verificada.
