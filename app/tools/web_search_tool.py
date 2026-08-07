import json
from typing import Optional
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import tool
from core.config import SERPER


def get_serper_wrapper(search_type: str = "search", k: int = 5) -> GoogleSerperAPIWrapper:
    """Retorna un objeto GoogleSerperAPIWrapper de LangChain Community configurado."""
    if not SERPER:
        raise ValueError("La variable de entorno SERPER_API_KEY no está configurada.")
    return GoogleSerperAPIWrapper(
        serper_api_key=SERPER,
        type=search_type,
        k=k,
        gl="gt",
        hl="es"
    )


@tool
def serper_web_search(query: str, search_type: str = "search", num_results: int = 5) -> str:
    """
    Ejecuta búsquedas en la web utilizando SERPER / Google Search (LangChain Community).
    Muestra los resultados relevantes con título, enlace y snippet.
    
    Args:
        query: Consulta o palabras clave de búsqueda.
        search_type: Tipo de búsqueda ('search' para web, 'videos' para videos, 'images' para imágenes).
        num_results: Cantidad de resultados a retornar (por defecto 5).
        
    Returns:
        Cadena en formato JSON con la lista de resultados encontrados (título, enlace, snippet, tipo).
    """
    if not SERPER:
        return json.dumps({
            "status": "error",
            "message": "La API Key de SERPER (SERPER_API_KEY) no está configurada en el archivo .env."
        }, ensure_ascii=False)

    try:
        wrapper = get_serper_wrapper(search_type=search_type, k=num_results)
        raw_results = wrapper.results(query)

        results = []
        stype = search_type.lower()
        if stype == "videos" and "videos" in raw_results:
            for item in raw_results["videos"][:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "tipo": "video"
                })
        elif stype == "images" and "images" in raw_results:
            for item in raw_results["images"][:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("imageUrl", item.get("link", "")),
                    "snippet": item.get("source", ""),
                    "tipo": "imagen"
                })
        else:
            organic = raw_results.get("organic", [])
            for item in organic[:num_results]:
                results.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "tipo": "sitio_web"
                })

        return json.dumps({
            "status": "success",
            "query": query,
            "search_type": search_type,
            "count": len(results),
            "results": results
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Error al ejecutar la búsqueda con LangChain SERPER: {str(e)}"
        }, ensure_ascii=False)
