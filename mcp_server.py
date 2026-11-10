from mcp.server.mcpserver import MCPServer
import requests
from bs4 import BeautifulSoup
import pandas as pd
from pathlib import Path

mcp = MCPServer("ScraperCuspide")

def _contiene_clase(clases, fragmento: str) -> bool:
    if not clases:
        return False
    nombres = [clases] if isinstance(clases, str) else clases
    return any(fragmento in nombre.casefold() for nombre in nombres)


@mcp.tool()
def extraer_top_cuspide(limite: int = 30) -> str:
    """Extrae el Top 100 de Cúspide, revisa los primeros 'limite' y guarda los nuevos en un CSV sin duplicar."""

    if limite <= 0:
        return "Error: El límite debe ser mayor que cero."

    url = "https://www.cuspide.com/100-mas-vendidos"
    directorio = Path(__file__).resolve().parent
    archivo_csv = directorio / "libros_cuspide.csv"
    archivo_debug = directorio / "debug_cuspide.html"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-AR,es;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        return f"Error de red al conectar con Cúspide: {e}"

    soup = BeautifulSoup(response.text, 'html.parser')

    libros_existentes = set()
    if archivo_csv.exists():
        try:
            df_existente = pd.read_csv(archivo_csv)
        except (OSError, UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as e:
            return f"Error: No se pudo leer {archivo_csv}: {e}. El archivo no fue modificado."

        if 'Titulo' not in df_existente.columns:
            return f"Error: {archivo_csv} no contiene la columna 'Titulo'. El archivo no fue modificado."

        libros_existentes = set(
            df_existente['Titulo'].dropna().astype(str).str.strip().str.casefold()
        )

    articulos = [
        ranking.parent
        for ranking in soup.select("p.livriz-ranking")
        if ranking.parent is not None
    ]

    if not articulos:
        try:
            archivo_debug.write_text(soup.prettify(), encoding="utf-8")
        except OSError as e:
            return f"Error: No se encontraron productos y tampoco se pudo guardar el HTML de diagnóstico: {e}"
        return (
            "Error: No se encontraron productos en la respuesta de Cúspide. "
            f"Puede haber cambiado el sitio o estar bloqueando la solicitud. Revisá {archivo_debug}."
        )

    nuevos_libros = []
    titulos_procesados = 0

    for articulo in articulos:
        if titulos_procesados >= limite:
            break

        tag_titulo = articulo.find(['h2', 'h3'])
        if not tag_titulo:
            tag_titulo = articulo.find(
                'a', class_=lambda clases: _contiene_clase(clases, 'title')
            )
        if not tag_titulo:
            tag_titulo = articulo.find(attrs={"itemprop": "name"})
        if not tag_titulo:
            continue

        titulo_limpio = tag_titulo.get_text(" ", strip=True)
        if not titulo_limpio:
            titulo_limpio = (tag_titulo.get("title") or tag_titulo.get("alt") or "").strip()
        if not titulo_limpio:
            continue

        tag_precio = articulo.find(
            class_=lambda clases: _contiene_clase(clases, 'price')
        )
        precio_limpio = (
            tag_precio.get_text(" ", strip=True) if tag_precio else "Precio no disponible"
        )
        titulo_comparacion = titulo_limpio.casefold()

        if titulo_comparacion not in libros_existentes:
            nuevos_libros.append({"Titulo": titulo_limpio, "Precio": precio_limpio})
            libros_existentes.add(titulo_comparacion)

        titulos_procesados += 1

    if not titulos_procesados:
        try:
            archivo_debug.write_text(soup.prettify(), encoding="utf-8")
        except OSError as e:
            return f"Error: Se encontraron productos, pero no se pudieron extraer títulos ni guardar el diagnóstico: {e}"
        return (
            "Error: Se encontraron elementos de producto, pero no se pudo extraer ningún título. "
            f"No se creó ni modificó el CSV. Revisá {archivo_debug}."
        )

    if nuevos_libros:
        df_nuevos = pd.DataFrame(nuevos_libros)
        try:
            df_nuevos.to_csv(
                archivo_csv,
                mode='a' if archivo_csv.exists() else 'w',
                header=not archivo_csv.exists(),
                index=False,
                encoding='utf-8',
            )
        except OSError as e:
            return f"Error: Se encontraron libros nuevos, pero no se pudo escribir {archivo_csv}: {e}"
        return (
            f"Éxito: Se procesaron {titulos_procesados} títulos. "
            f"Filas nuevas agregadas: {len(nuevos_libros)}. Archivo: {archivo_csv}."
        )

    return (
        f"Finalizado sin cambios: Se procesaron {titulos_procesados} títulos y todos ya estaban "
        f"en {archivo_csv}. No se agregaron filas."
    )

if __name__ == "__main__":
    mcp.run()