import json
from typing import List, Dict, Any
from bson import ObjectId
from pymongo import MongoClient
from langchain_core.tools import tool
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from core.config import get_env_variable
from core.collections import VECTORS, SUB_AREAS


def get_db():
    """
    Obtains the MongoDB database connection.

    Returns:
        Database: MongoDB database instance.
    """
    mongodb_uri = get_env_variable("MONGODB_URI")
    db_name = get_env_variable("DB_NAME")
    client = MongoClient(mongodb_uri)
    return client[db_name]


def get_embedding_model() -> GoogleGenerativeAIEmbeddings:
    """
    Instantiates the Google Generative AI Embeddings model.

    Returns:
        GoogleGenerativeAIEmbeddings: Configured embeddings model.
    """
    google_api_key = get_env_variable("GOOGLE_API_KEY")
    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-2",
        google_api_key=google_api_key,
        output_dimensionality=768
    )


def generate_embedding(text: str) -> List[float]:
    """
    Generates the embedding vector for a given text.

    Args:
        text (str): Text to vectorize.

    Returns:
        List[float]: Numerical embedding vector.
    """
    embeddings_model = get_embedding_model()
    return embeddings_model.embed_query(text)


def get_vector_store() -> MongoDBAtlasVectorSearch:
    """
    Obtains the vector search instance over the vectors collection.

    Returns:
        MongoDBAtlasVectorSearch: Configured vector store.
    """
    db = get_db()
    collection = db[VECTORS]
    embeddings_model = get_embedding_model()

    return MongoDBAtlasVectorSearch(
        collection=collection,
        embedding=embeddings_model,
        index_name="vector_index_cnb",
        text_key="texto_a_buscar",
        embedding_key="vector_embedding",
        relevance_score_fn="cosine"
    )


def generate_and_store_subarea_embeddings(id_subarea_relacionada: str) -> Dict[str, Any]:
    """
    Generates and stores vector embeddings for the nodes of a curricular subarea.

    Args:
        id_subarea_relacionada (str): Identifier of the curricular subarea.

    Returns:
        Dict[str, Any]: Execution result containing status and count of processed vectors.
    """
    try:
        db = get_db()
        subarea_id = ObjectId(id_subarea_relacionada.strip())

        query = {
            "id_subarea_relacionada": subarea_id,
            "vector_estado": False
        }
        docs = list(db[VECTORS].find(query))

        if not docs:
            return {"status": "info", "message": "No pending nodes to vectorize found for this subarea."}

        embeddings_model = get_embedding_model()
        texts = [doc["texto_a_buscar"] for doc in docs]
        vectors = embeddings_model.embed_documents(texts)

        updated_count = 0
        for doc, vector in zip(docs, vectors):
            db[VECTORS].update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {
                        "vector_embedding": vector,
                        "vector_estado": True
                    }
                }
            )
            updated_count += 1

        return {
            "status": "success",
            "message": f"Successfully vectorized {updated_count} subarea nodes.",
            "vectores_actualizados": updated_count
        }

    except Exception as e:
        return {"status": "error", "message": f"Error generating embeddings: {str(e)}"}


def vector_search_cnb(
    query: str,
    id_subarea_relacionada: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Performs a semantic vector search filtered by curricular subarea.

    Args:
        query (str): Text or semantic query to search for.
        id_subarea_relacionada (str): Mandatory curricular subarea identifier.
        limit (int, optional): Maximum number of results to return. Defaults to 5.

    Returns:
        List[Dict[str, Any]]: List of top matching curricular nodes.
    """
    if not id_subarea_relacionada or not str(id_subarea_relacionada).strip():
        raise ValueError("Parameter 'id_subarea_relacionada' (24-char ObjectId) is required to perform vector search.")

    subarea_str = str(id_subarea_relacionada).strip()
    if len(subarea_str) != 24:
        raise ValueError("Parameter 'id_subarea_relacionada' must be a valid 24-character hex MongoDB ObjectId.")

    db = get_db()
    query_vector = generate_embedding(query)

    vector_search_stage: Dict[str, Any] = {
        "index": "vector_index_cnb",
        "path": "vector_embedding",
        "queryVector": query_vector,
        "numCandidates": limit * 10,
        "limit": limit,
        "filter": {
            "id_subarea_relacionada": {
                "$eq": ObjectId(subarea_str)
            }
        }
    }

    pipeline = [
        {"$vectorSearch": vector_search_stage},
        {
            "$project": {
                "_id": 1,
                "id_subarea_relacionada": 1,
                "nombre_subarea": 1,
                "tipo_nodo": 1,
                "referencia_jerarquica": 1,
                "texto_a_buscar": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]

    cursor = db[VECTORS].aggregate(pipeline)
    results = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["id_subarea_relacionada"] = str(doc["id_subarea_relacionada"])
        results.append(doc)

    return results


def fetch_subarea_nodes_from_db(vector_results: List[Dict[str, Any]], db=None) -> List[Dict[str, Any]]:
    """
    Retrieves full hierarchical subarea nodes from database based on vector search results.

    Args:
        vector_results (List[Dict[str, Any]]): Results obtained from vector search.
        db (optional): MongoDB database instance.

    Returns:
        List[Dict[str, Any]]: List of mapped nodes with competency, indicator, and content.
    """
    if not vector_results:
        return []

    if db is None:
        try:
            db = get_db()
        except Exception:
            db = None

    matched_nodes = []
    subarea_docs = {}

    for item in vector_results:
        sub_id_str = str(item.get("id_subarea_relacionada", "")).strip()
        tipo_nodo = str(item.get("tipo_nodo", "")).strip().lower()
        texto_a_buscar = str(item.get("texto_a_buscar", "")).strip()

        subarea_doc = None
        if db is not None and sub_id_str:
            if sub_id_str not in subarea_docs:
                try:
                    obj_id = ObjectId(sub_id_str)
                    doc = db[SUB_AREAS].find_one({"_id": obj_id})
                    subarea_docs[sub_id_str] = doc
                except Exception:
                    subarea_docs[sub_id_str] = None
            subarea_doc = subarea_docs.get(sub_id_str)

        node_data = {
            "id_subarea_relacionada": sub_id_str,
            "tipo_nodo": tipo_nodo,
            "texto_a_buscar": texto_a_buscar,
            "competencia": None,
            "indicador": None,
            "contenido": None,
            "all_contenidos_indicador": []
        }

        if subarea_doc and "competencias" in subarea_doc:
            found = False
            for comp in subarea_doc.get("competencias", []):
                comp_desc = str(comp.get("descripcion", "")).strip()
                comp_id = str(comp.get("id_competencia", "")).strip()
                comp_full = f"competencia {comp_id}: {comp_desc}".lower()

                if tipo_nodo == "competencia" and (
                    comp_desc.lower() == texto_a_buscar.lower() or
                    comp_full == texto_a_buscar.lower()
                ):
                    node_data["competencia"] = {"id_competencia": comp_id, "descripcion": comp_desc}
                    full_ind_list = []
                    for ind in comp.get("indicadores_logro", []):
                        ind_id = str(ind.get("id_indicador", "")).strip()
                        ind_desc = str(ind.get("descripcion", "")).strip()
                        cnts_list = []
                        for c in ind.get("contenidos", []):
                            if isinstance(c, dict):
                                cnts_list.append({
                                    "id_contenido": str(c.get("id_contenido", "")).strip(),
                                    "descripcion": str(c.get("descripcion", "")).strip()
                                })
                            else:
                                cnts_list.append({"id_contenido": "", "descripcion": str(c).strip()})
                        full_ind_list.append({
                            "id_indicador": ind_id,
                            "indicador": ind_desc,
                            "contenidos": cnts_list
                        })
                    node_data["full_competencia_tree"] = full_ind_list
                    found = True
                    break

                for ind in comp.get("indicadores_logro", []):
                    ind_desc = str(ind.get("descripcion", "")).strip()
                    ind_id = str(ind.get("id_indicador", "")).strip()
                    ind_full = f"indicador {ind_id}: {ind_desc}".lower()

                    if tipo_nodo == "indicador" and (
                        ind_desc.lower() == texto_a_buscar.lower() or
                        ind_full == texto_a_buscar.lower()
                    ):
                        node_data["competencia"] = {"id_competencia": comp_id, "descripcion": comp_desc}
                        node_data["indicador"] = {"id_indicador": ind_id, "descripcion": ind_desc}
                        cnts_list = []
                        for c in ind.get("contenidos", []):
                            if isinstance(c, dict):
                                cnts_list.append({
                                    "id_contenido": str(c.get("id_contenido", "")).strip(),
                                    "descripcion": str(c.get("descripcion", "")).strip()
                                })
                            else:
                                cnts_list.append({"id_contenido": "", "descripcion": str(c).strip()})
                        node_data["all_contenidos_indicador"] = cnts_list
                        found = True
                        break

                    for cnt in ind.get("contenidos", []):
                        cnt_desc = str(cnt.get("descripcion", "") if isinstance(cnt, dict) else str(cnt)).strip()
                        cnt_id = str(cnt.get("id_contenido", "") if isinstance(cnt, dict) else "").strip()
                        cnt_full = f"contenido {cnt_id}: {cnt_desc}".lower()

                        if tipo_nodo == "contenido" and (
                            cnt_desc.lower() == texto_a_buscar.lower() or
                            cnt_full == texto_a_buscar.lower()
                        ):
                            node_data["competencia"] = {"id_competencia": comp_id, "descripcion": comp_desc}
                            node_data["indicador"] = {"id_indicador": ind_id, "descripcion": ind_desc}
                            node_data["contenido"] = {"id_contenido": cnt_id, "descripcion": cnt_desc}
                            found = True
                            break
                    if found:
                        break
                if found:
                    break

        if not node_data["competencia"] and not node_data["indicador"] and not node_data["contenido"]:
            if tipo_nodo == "competencia":
                node_data["competencia"] = {"id_competencia": "", "descripcion": texto_a_buscar}
            elif tipo_nodo == "indicador":
                node_data["indicador"] = {"id_indicador": "", "descripcion": texto_a_buscar}
            elif tipo_nodo == "contenido":
                node_data["contenido"] = {"id_contenido": "", "descripcion": texto_a_buscar}

        matched_nodes.append(node_data)

    return matched_nodes


def build_merged_curriculum_tree(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Builds a unified tree structure from a list of curricular nodes.

    Args:
        elements (List[Dict[str, Any]]): List of curricular nodes.

    Returns:
        List[Dict[str, Any]]: Unified hierarchical tree structure for the subarea.
    """
    if not elements:
        return []

    competencias_map = {}

    for elem in elements:
        comp = elem.get("competencia")
        ind = elem.get("indicador")
        cnt = elem.get("contenido")
        all_cnts = elem.get("all_contenidos_indicador", [])
        full_comp_tree = elem.get("full_competencia_tree", [])

        if not comp or not comp.get("descripcion"):
            continue

        comp_desc = comp["descripcion"].strip()
        comp_id = str(comp.get("id_competencia", "")).strip()
        comp_key = comp_desc.lower()

        if comp_key not in competencias_map:
            competencias_map[comp_key] = {
                "id_competencia": comp_id,
                "competencia": comp_desc,
                "indicadores": {},
                "full_competencia_tree": []
            }
        elif comp_id and not competencias_map[comp_key]["id_competencia"]:
            competencias_map[comp_key]["id_competencia"] = comp_id

        if full_comp_tree and not competencias_map[comp_key]["full_competencia_tree"]:
            competencias_map[comp_key]["full_competencia_tree"] = full_comp_tree

        if ind and ind.get("descripcion"):
            ind_desc = ind["descripcion"].strip()
            ind_id = str(ind.get("id_indicador", "")).strip()
            ind_key = ind_desc.lower()

            if ind_key not in competencias_map[comp_key]["indicadores"]:
                competencias_map[comp_key]["indicadores"][ind_key] = {
                    "id_indicador": ind_id,
                    "indicador": ind_desc,
                    "contenidos": [],
                    "all_contenidos_fallback": []
                }
            elif ind_id and not competencias_map[comp_key]["indicadores"][ind_key]["id_indicador"]:
                competencias_map[comp_key]["indicadores"][ind_key]["id_indicador"] = ind_id

            if all_cnts and not competencias_map[comp_key]["indicadores"][ind_key]["all_contenidos_fallback"]:
                competencias_map[comp_key]["indicadores"][ind_key]["all_contenidos_fallback"] = all_cnts

            if cnt and cnt.get("descripcion"):
                cnt_desc = cnt["descripcion"].strip()
                cnt_id = str(cnt.get("id_contenido", "")).strip()

                cnt_list = competencias_map[comp_key]["indicadores"][ind_key]["contenidos"]
                exists = any(
                    c.get("descripcion", "").lower() == cnt_desc.lower() or
                    (cnt_id and c.get("id_contenido") == cnt_id)
                    for c in cnt_list
                )
                if not exists:
                    cnt_list.append({
                        "id_contenido": cnt_id,
                        "descripcion": cnt_desc
                    })

    for comp_info in competencias_map.values():
        if len(comp_info["indicadores"]) == 0 and comp_info.get("full_competencia_tree"):
            for ind_item in comp_info["full_competencia_tree"]:
                ind_desc = ind_item["indicador"].strip()
                ind_id = ind_item["id_indicador"].strip()
                ind_key = ind_desc.lower()
                comp_info["indicadores"][ind_key] = {
                    "id_indicador": ind_id,
                    "indicador": ind_desc,
                    "contenidos": ind_item["contenidos"],
                    "all_contenidos_fallback": []
                }

    for comp_info in competencias_map.values():
        for ind_info in comp_info["indicadores"].values():
            if len(ind_info["contenidos"]) == 0 and ind_info.get("all_contenidos_fallback"):
                ind_info["contenidos"] = ind_info["all_contenidos_fallback"]

    arbol_final = []
    for comp_info in competencias_map.values():
        indicadores_list = []
        for ind_info in comp_info["indicadores"].values():
            indicadores_list.append({
                "id_indicador": ind_info["id_indicador"],
                "indicador": ind_info["indicador"],
                "contenidos": ind_info["contenidos"]
            })
        arbol_final.append({
            "id_competencia": comp_info["id_competencia"],
            "competencia": comp_info["competencia"],
            "indicadores": indicadores_list
        })

    return arbol_final


@tool("search_curriculum_vector_db")
def search_curriculum_vector_db(query: str, id_subarea_relacionada: str, limit: int = 5) -> str:
    """
    Searches semantic information in the curriculum vector database by subarea.

    Args:
        query (str): Semantic query, topic, or competency to search for.
        id_subarea_relacionada (str): Mandatory identifier of the curricular subarea.
        limit (int, optional): Limit of results to return. Defaults to 5.

    Returns:
        str: JSON formatted string containing the retrieved unified curricular tree.
    """
    try:
        raw_results = vector_search_cnb(query=query, id_subarea_relacionada=id_subarea_relacionada, limit=limit)

        db = None
        try:
            db = get_db()
        except Exception:
            pass

        elements = fetch_subarea_nodes_from_db(raw_results, db=db)
        arbol_curricular = build_merged_curriculum_tree(elements)

        return json.dumps({
            "status": "success",
            "query": query,
            "id_subarea_relacionada": id_subarea_relacionada.strip(),
            "arbol_curricular": arbol_curricular
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Error in MongoDB vector search: {str(e)}"
        }, ensure_ascii=False)


@tool("generate_subarea_vector_embeddings")
def generate_subarea_vector_embeddings(id_subarea_relacionada: str) -> str:
    """
    Generates vector embeddings for all pending nodes of a subarea.

    Args:
        id_subarea_relacionada (str): Identifier of the subarea to vectorize.

    Returns:
        str: JSON formatted string with the vectorization process report.
    """
    res = generate_and_store_subarea_embeddings(id_subarea_relacionada)
    return json.dumps(res, ensure_ascii=False, indent=2)
