# daily_reporting · Seguimiento de ventas

Dashboard de facturación y venta interna (Toyota / Hino) a partir de los Excel diarios del sistema.
Definiciones: `CONTEXTO.md` · Metodología y controles: `PLAN.md` · Reglas de trabajo: `CLAUDE.md`.

## Estructura

```
daily_reporting/
├── actualizar.py              Un paso: prepara datos + genera HTML (+ publica con --publicar)
├── actualizar_y_publicar.bat  Doble clic en Windows = python actualizar.py --publicar
├── requirements.txt
├── procesamiento/             Preparación automática (reemplaza la corrida manual del notebook)
│   ├── config.py              Hojas, columnas, tipos, clave, columnas publicadas
│   ├── preparacion.py         Lee, valida, guarda historial y publica
│   └── test_preparacion.py
├── dashboard/
│   ├── app.py                 App Streamlit (3 pestañas)
│   ├── config.py              Meta, tipos excluidos, canales, marcas, feriados
│   ├── indicadores.py         Cálculos (funciones puras)
│   ├── graficos.py            Figuras Plotly
│   ├── reporte_html.py        Reporte HTML autocontenido
│   ├── datos.py               Lectura de data/publicado/
│   └── test_indicadores.py
├── data/
│   ├── originales/            Excel del sistema (NO se suben a GitHub)
│   ├── preparados/            Historial local validado + registro + resumen (NO se sube)
│   └── publicado/             Lo que usa el dashboard: CSV validados sin datos personales + estado.json (SÍ se sube)
├── reportes/                  Reportes HTML generados (NO se suben)
└── notebooks/01_preparacion.ipynb   Exploración/auditoría (opcional; ya no es necesario correrlo)
```

## Instalación (una vez)

```bash
pip install -r requirements.txt
```

## Uso diario (local)

1. Reemplaza `inf_fact.xlsx` e `inf_venta_int.xlsx` en `data/originales/`.
2. Abre el dashboard:
   ```bash
   streamlit run dashboard/app.py
   ```
   Al abrir, detecta si los Excel cambiaron y los prepara solo. Si alguna validación falla (p. ej. cambió un día ya
   reportado), muestra un aviso y sigue con los últimos datos válidos. Botones en la barra lateral:
   **🔄 Reprocesar datos**, **Aceptar cambios en la historia** (solo si corresponde) y **⬇️ Descargar reporte HTML**.

Sin abrir la app: `python actualizar.py` (prepara + genera `reportes/reporte_ventas_hasta_AAAAMMDD.html`).

## Reporte HTML (para compartir por WhatsApp, correo, Teams)

- Se genera con `python actualizar.py` o con el botón **⬇️ Descargar reporte HTML** (para la fecha de corte elegida).
- Es **un solo archivo** (~5 MB) con las 3 pestañas y gráficos interactivos; funciona sin internet.
- Se abre con el navegador (Chrome, Edge, Safari). En celular: descargar y abrir con el navegador
  (algunas vistas previas de apps de mensajería no ejecutan los gráficos).
- Es una foto de la fecha de corte: para datos nuevos, generar y reenviar.

## Publicar 24/7 (GitHub + Streamlit Community Cloud)

> ⚠️ Con un repositorio **público**, cualquier persona en internet puede ver el código y `data/publicado/`
> (facturación, venta interna, modelos, asesores). No se suben los Excel, el historial ni datos de clientes
> (ver `.gitignore`). Si más adelante quieres restringir el acceso, cambia el repo a privado e invita correos en Streamlit.

### Configuración inicial (una sola vez)

1. Crea una cuenta en <https://github.com> y un repositorio vacío (p. ej. `seguimiento-ventas`), **sin** README.
2. Instala Git (<https://git-scm.com>) y, en esta carpeta:
   ```bash
   python actualizar.py
   git init
   git add .
   git commit -m "Dashboard de seguimiento de ventas"
   git branch -M main
   git remote add origin https://github.com/<tu-usuario>/seguimiento-ventas.git
   git push -u origin main
   ```
   Antes del `commit`, revisa con `git status` que **no** aparezcan `data/originales`, `data/preparados`, `reportes` ni `.xlsx`.
3. Entra a <https://share.streamlit.io> con tu cuenta de GitHub → **Create app** → elige el repositorio,
   rama `main`, archivo principal `dashboard/app.py` → **Deploy**.
4. Comparte la URL `https://<nombre>.streamlit.app` con tu equipo.

### Actualizar lo publicado (cada vez que tengas Excel nuevos)

1. Reemplaza los Excel en `data/originales/`.
2. Doble clic en **`actualizar_y_publicar.bat`** (o `python actualizar.py --publicar`).
   Prepara, valida, genera el HTML y sube `data/publicado/` a GitHub. Streamlit Cloud se actualiza en 1–2 minutos.
   Si una validación falla, no se publica nada nuevo para ese archivo.

Nota: si nadie abre la app por varios días, Streamlit Cloud la pone en reposo; el primer acceso la despierta
(tarda un poco).

## Pruebas (datos sintéticos)

```bash
pytest procesamiento dashboard
```
