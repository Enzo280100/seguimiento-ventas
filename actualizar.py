"""Actualiza todo en un paso: prepara los Excel nuevos, genera el reporte HTML y (opcional) publica en GitHub.

Uso (desde la raíz del proyecto):
    python actualizar.py                 # prepara datos + genera reportes/reporte_ventas_hasta_AAAAMMDD.html
    python actualizar.py --publicar      # además sube data/publicado/ a GitHub (Streamlit Cloud se actualiza solo)
    python actualizar.py --forzar        # reprocesa aunque los Excel no hayan cambiado
    python actualizar.py --aceptar-cambios-historia   # acepta que los Excel nuevos modificaron días ya reportados
"""
import argparse
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "dashboard"))
sys.path.insert(1, str(RAIZ))

from procesamiento import preparacion  # noqa: E402
from reporte_html import generar_reporte  # noqa: E402


def git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)


def publicar(mensaje: str) -> bool:
    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        print("[PUBLICAR] Esta carpeta no es un repositorio git. Sigue los pasos de README.md (sección Publicar).")
        return False
    git("add", "data/publicado")
    if git("diff", "--cached", "--quiet").returncode == 0:
        print("[PUBLICAR] Sin cambios en data/publicado: nada que subir.")
        return True
    c = git("commit", "-m", mensaje)
    if c.returncode != 0:
        print("[PUBLICAR] Error al hacer commit:", c.stderr.strip() or c.stdout.strip())
        return False
    p = git("push")
    if p.returncode != 0:
        print("[PUBLICAR] Error al subir (git push):", p.stderr.strip())
        return False
    print("[PUBLICAR] Datos subidos. Streamlit Cloud se actualizará en 1–2 minutos.")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--publicar", action="store_true")
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--aceptar-cambios-historia", action="store_true")
    ap.add_argument("--sin-html", action="store_true")
    a = ap.parse_args()

    resultados = preparacion.preparar(RAIZ, forzar=a.forzar, aceptar_cambios_historia=a.aceptar_cambios_historia)
    ok = True
    for nombre, r in resultados.items():
        estado = r.get("estado")
        extra = "" if r.get("reprocesado") else " (sin cambios)"
        detalle = f"hasta {r.get('fecha_max')} · {r.get('filas', 0):,} filas" if estado == "COMPLETO" else \
            (", ".join(r.get("validaciones_fallidas", [])) or r.get("mensaje", ""))
        print(f"[{estado}] {nombre}{extra}: {detalle}")
        ok &= estado == "COMPLETO"
    if not ok:
        print("Algún archivo no pasó las validaciones: se mantienen publicados los últimos datos válidos. "
              "Detalle en data/preparados/resumen_preparacion.md")

    if not a.sin_html:
        try:
            ruta = generar_reporte(RAIZ / "data" / "publicado")
            print(f"[HTML] {ruta.relative_to(RAIZ)}")
        except ValueError as e:
            print(f"[HTML] No generado: {e}")

    if a.publicar:
        fechas = [r.get("fecha_max") for r in resultados.values() if r.get("estado") == "COMPLETO"]
        publicar(f"Actualiza datos hasta {max(fechas) if fechas else 'sin cambios válidos'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
