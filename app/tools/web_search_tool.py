import json
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.tools import tool
from core.config import get_env_variable
from middleware.security_middleware import sanitize_external_text


def get_serper_wrapper(search_type: str = "search", k: int = 5) -> GoogleSerperAPIWrapper:
    """
    Creates an instance of the GoogleSerperAPIWrapper search client.

    Args:
        search_type (str): Type of search ('search', 'videos', 'images').
        k (int): Number of desired results.

    Returns:
        GoogleSerperAPIWrapper: Configured search client instance.
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
    Performs web searches using the Serper Google Search engine.

    Args:
        query (str): Search query or keywords.
        search_type (str, optional): Search type ('search', 'videos', 'images'). Defaults to 'search'.
        num_results (int, optional): Number of results to return. Defaults to 5.

    Returns:
        str: JSON formatted string containing the list of search results (title, link, snippet, type).
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
            "message": f"Error executing web search: {str(e)}"
        }, ensure_ascii=False)
