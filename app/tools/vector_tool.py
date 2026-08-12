import os
import json
from typing import List, Dict, Any, Optional
from bson import ObjectId
from pymongo import MongoClient
from langchain_core.tools import tool
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from core.config import MONGODB_URI, DB_NAME, GOOGLE
from core.collections import VECTORES, SUBAREAS
from core.tool_inputs import (
    SearchCurriculumVectorDBInput,
    GenerateSubareaVectorEmbeddingsInput,
)


def get_db():
    """Retorna la base de datos de MongoDB a partir de DB_NAME o la base por defecto de MONGODB_URI."""
    if not MONGODB_URI:
        raise ValueError("La variable MONGODB_URI no está configurada.")
    client = MongoClient(MONGODB_URI)
    if DB_NAME:
        return client[DB_NAME]
    try:
        db = client.get_default_database()
        if db is not None:
            return db
    except Exception:
        pass
    raise ValueError("No se especificó la base de datos de MongoDB. Configura DB_NAME en .env o inclúyela en la MONGODB_URI.")


def get_embedding_model() -> GoogleGenerativeAIEmbeddings:
    """Instancia el modelo oficial de embeddings de Google Gemini (text-embedding-004 de 768 dimensiones)."""
    if not GOOGLE:
        raise ValueError("La clave de API GOOGLE_API_KEY (GOOGLE en core.config) no está configurada en .env.")
    return GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-005",
        google_api_key=GOOGLE
    )


def generate_embedding(text: str) -> List[float]:
    """Genera un vector de 768 dimensiones para el texto proporcionado mediante Google Gemini API."""
    embeddings_model = get_embedding_model()
    return embeddings_model.embed_query(text)


def get_vector_store() -> MongoDBAtlasVectorSearch:
    """
    Crea una instancia de MongoDBAtlasVectorSearch (LangChain MongoDB) sobre la colección VECTORES.
    """
    db = get_db()
    collection = db[VECTORES]
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
    Genera y guarda embeddings de 768 dimensiones en VECTORES para todos los nodos de una subárea.
    
    Args:
        id_subarea_relacionada (str): ID de la subárea en SUBAREAS.
        
    Returns:
        dict: Resultado con la cantidad de vectores actualizados.
    """
    try:
        db = get_db()
        subarea_id = ObjectId(id_subarea_relacionada.strip())

        query = {
            "id_subarea_relacionada": subarea_id,
            "vector_estado": False
        }
        docs = list(db[VECTORES].find(query))

        if not docs:
            return {"status": "info", "message": "No se encontraron nodos pendientes de vectorizar para esta subárea."}

        embeddings_model = get_embedding_model()
        texts = [doc["texto_a_buscar"] for doc in docs]
        vectors = embeddings_model.embed_documents(texts)

        updated_count = 0
        for doc, vector in zip(docs, vectors):
            db[VECTORES].update_one(
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
            "message": f"Se vectorizaron exitosamente {updated_count} nodos de la subárea.",
            "vectores_actualizados": updated_count
        }

    except Exception as e:
        return {"status": "error", "message": f"Error al generar embeddings: {str(e)}"}


def vector_search_cnb(
    query: str,
    id_subarea_relacionada: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Ejecuta el pipeline de agregación '$vectorSearch' en MongoDB Atlas Search sobre la colección VECTORES.
    El parámetro 'id_subarea_relacionada' es OBLIGATORIO para filtrar estrictamente por subárea.
    """
    if not id_subarea_relacionada or not str(id_subarea_relacionada).strip():
        raise ValueError("El parámetro 'id_subarea_relacionada' (ObjectId de 24 caracteres) es obligatorio para realizar la búsqueda vectorial.")

    subarea_str = str(id_subarea_relacionada).strip()
    if len(subarea_str) != 24:
        raise ValueError("El 'id_subarea_relacionada' debe ser un ObjectId de MongoDB válido de 24 caracteres hexadecimales.")

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

    cursor = db[VECTORES].aggregate(pipeline)
    results = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["id_subarea_relacionada"] = str(doc["id_subarea_relacionada"])
        results.append(doc)

    return results


@tool("search_curriculum_vector_db", args_schema=SearchCurriculumVectorDBInput)
def search_curriculum_vector_db(query: str, id_subarea_relacionada: str, limit: int = 10) -> str:
    """
    Realiza una búsqueda semántica vectorial ($vectorSearch) sobre el Currículum Nacional Base (CNB) en MongoDB.
    El parámetro 'id_subarea_relacionada' es OBLIGATORIO para delimitar la búsqueda a la subárea curricular correspondiente.
    
    Args:
        query (str): Tema, competencia o contenido a buscar.
        id_subarea_relacionada (str): ID OBLIGATORIO de la subárea (ObjectId de 24 caracteres hexadecimales).
        limit (int): Número máximo de resultados a retornar.
        
    Returns:
        str: Cadena en formato JSON con las coincidencias semánticas encontradas y su puntuación de relevancia.
    """
    try:
        results = vector_search_cnb(query=query, id_subarea_relacionada=id_subarea_relacionada, limit=limit)

        return json.dumps({
            "status": "success",
            "query": query,
            "id_subarea_relacionada": id_subarea_relacionada.strip(),
            "count": len(results),
            "results": results
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Error en la búsqueda vectorial de MongoDB: {str(e)}"
        }, ensure_ascii=False)


@tool("generate_subarea_vector_embeddings", args_schema=GenerateSubareaVectorEmbeddingsInput)
def generate_subarea_vector_embeddings(id_subarea_relacionada: str) -> str:
    """
    Genera y actualiza los embeddings vectoriales (768d) para todos los nodos de una subárea en VECTORES.
    
    Args:
        id_subarea_relacionada (str): ID de la subárea a vectorizar.
        
    Returns:
        str: JSON con el resultado del proceso de vectorización.
    """
    res = generate_and_store_subarea_embeddings(id_subarea_relacionada)
    return json.dumps(res, ensure_ascii=False, indent=2)
