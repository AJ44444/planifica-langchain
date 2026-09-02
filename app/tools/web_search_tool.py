import json
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import tool
from core.config import get_env_variable
from middleware.security_middleware import sanitize_external_text


def get_serper_wrapper(search_type: str = "search", k: int = 5) -> GoogleSerperAPIWrapper:
    """
    Crea una instancia del cliente de búsqueda GoogleSerperAPIWrapper.

    Args:
        search_type (str): Tipo de búsqueda ('search', 'videos', 'images').
        k (int): Cantidad de resultados deseados.

    Returns:
        GoogleSerperAPIWrapper: Cliente de búsqueda configurado.
    """
    serper_key = get_env_variable("SERPER_API_KEY")
    return GoogleSerperAPIWrapper(
        serper_api_key=serper_key,
        type=search_type,
        k=k,
        gl="gt",
        hl="es"
    )


@tool("serper_web_search")
def serper_web_search(query: str, search_type: str = "search", num_results: int = 5) -> str:
    """
    Realiza búsquedas en la web utilizando el motor Serper Google Search.

    Args:
        query (str): Consulta o palabras clave de búsqueda.
        search_type (str, opcional): Tipo de búsqueda ('search', 'videos', 'images'). Por defecto 'search'.
        num_results (int, opcional): Cantidad de resultados a retornar. Por defecto 5.

    Returns:
        str: Cadena en formato JSON con la lista de resultados encontrados (título, enlace, snippet, tipo).
    """
    try:
        serper_key = get_env_variable("SERPER_API_KEY")
        wrapper = get_serper_wrapper(search_type=search_type, k=num_results)
        raw_results = wrapper.results(query)

        results = []
        stype = search_type.lower()
        if stype == "videos" and "videos" in raw_results:
            for item in raw_results["videos"][:num_results]:
                results.append({
                    "title": sanitize_external_text(item.get("title", "")),
                    "link": item.get("link", ""),
                    "snippet": sanitize_external_text(item.get("snippet", "")),
                    "tipo": "video"
                })
        elif stype == "images" and "images" in raw_results:
            for item in raw_results["images"][:num_results]:
                results.append({
                    "title": sanitize_external_text(item.get("title", "")),
                    "link": item.get("imageUrl", item.get("link", "")),
                    "snippet": sanitize_external_text(item.get("source", "")),
                    "tipo": "imagen"
                })
        else:
            organic = raw_results.get("organic", [])
            for item in organic[:num_results]:
                results.append({
                    "title": sanitize_external_text(item.get("title", "")),
                    "link": item.get("link", ""),
                    "snippet": sanitize_external_text(item.get("snippet", "")),
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
            "message": f"Error al ejecutar la búsqueda: {str(e)}"
        }, ensure_ascii=False)
