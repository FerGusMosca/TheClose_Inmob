# common/util/search/property_searcher.py
"""
Bi-encoder semantic search against pgvector.
Converts user query → embedding → cosine similarity search in DB.
Optionally combines with SQL filters (neighborhood, price, ambientes).
All comments in English.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from business_entities.property import Property

log = logging.getLogger(__name__)

_DEFAULT_TOP_K = 8


@dataclass
class SearchContext:
    """Carries matched properties and the original query for the LLM."""
    query:      str
    properties: list[Property]
    top_k:      int


class PropertySearcher:
    """
    Semantic property search using OpenAI embeddings + pgvector cosine similarity.
    Supports optional SQL filters applied alongside the vector search.
    """

    EMBEDDING_MODEL = "text-embedding-3-small"

    def __init__(self, database_url: str, openai_api_key: str, top_k: int = _DEFAULT_TOP_K):
        self.database_url = database_url
        self.top_k        = top_k
        self._openai      = OpenAI(api_key=openai_api_key)

    # ── Public interface ──────────────────────────────────────────────────────

    def search(
        self,
        query:        str,
        neighborhood: Optional[str]   = None,
        ambientes:    Optional[int]   = None,
        price_max:    Optional[float] = None,
        top_k:        Optional[int]   = None,
    ) -> SearchContext:
        k = top_k or self.top_k
        log.info("PropertySearcher.search | query=%r neighborhood=%s top_k=%d", query, neighborhood, k)
        query_vector = self._embed(query)
        properties   = self._vector_search(query_vector, neighborhood, ambientes, price_max, k)
        log.info("PropertySearcher.search | found=%d", len(properties))
        return SearchContext(query=query, properties=properties, top_k=k)

    # ── Embedding ─────────────────────────────────────────────────────────────

    def _embed(self, text: str) -> list[float]:
        response = self._openai.embeddings.create(
            model=self.EMBEDDING_MODEL,
            input=[text],
        )
        return response.data[0].embedding

    # ── Vector search ─────────────────────────────────────────────────────────

    def _vector_search(
        self,
        query_vector: list[float],
        neighborhood: Optional[str],
        ambientes:    Optional[int],
        price_max:    Optional[float],
        top_k:        int,
    ) -> list[Property]:
        """
        Runs pgvector cosine similarity (<=> operator) with optional SQL filters.
        Lower distance = better match.
        """
        import psycopg2

        filters = ["e.embedding IS NOT NULL"]
        params  = []

        if neighborhood:
            filters.append("n.slug = %s")
            params.append(neighborhood)
        if ambientes:
            filters.append("p.ambientes = %s")
            params.append(ambientes)
        if price_max:
            filters.append("l.price <= %s")
            params.append(price_max)

        where_clause = " AND ".join(filters)
        vector_str   = "[" + ",".join(str(v) for v in query_vector) + "]"

        sql = f"""
            SELECT
                p.id,
                p.title,
                p.address,
                n.name              AS neighborhood,
                c.name              AS city,
                pt.code             AS property_type,
                p.ambientes,
                p.dormitorios,
                p.banos,
                p.m2_total,
                p.m2_cover,
                l.price,
                l.currency,
                l.expensas,
                l.expensas_currency,
                s.code              AS source,
                l.portal_id,
                l.url,
                lt.code             AS listing_type,
                l.status,
                e.embedding <=> %s::vector AS distance
            FROM properties      p
            JOIN embeddings      e  ON e.property_id  = p.id
            JOIN neighborhoods   n  ON n.id           = p.neighborhood_id
            JOIN cities          c  ON c.id           = n.city_id
            JOIN property_types  pt ON pt.id          = p.property_type_id
            LEFT JOIN listings   l  ON l.property_id  = p.id
            LEFT JOIN sources    s  ON s.id           = l.source_id
            LEFT JOIN listing_types lt ON lt.id       = l.listing_type_id
            WHERE {where_clause}
            ORDER BY distance ASC
            LIMIT %s
        """

        all_params = [vector_str] + params + [top_k]

        conn = psycopg2.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, all_params)
                rows = cur.fetchall()
        finally:
            conn.close()

        return [self._row_to_property(row) for row in rows]

    @staticmethod
    def _row_to_property(row) -> Property:
        return Property(
            id                = row[0],
            title             = row[1],
            address           = row[2],
            neighborhood      = row[3],
            city              = row[4],
            property_type     = row[5],
            ambientes         = row[6],
            dormitorios       = row[7],
            banos             = row[8],
            m2_total          = float(row[9])  if row[9]  else None,
            m2_cover          = float(row[10]) if row[10] else None,
            price             = float(row[11]) if row[11] else None,
            currency          = row[12],
            expensas          = float(row[13]) if row[13] else None,
            expensas_currency = row[14],
            source            = row[15],
            portal_id         = row[16],
            url               = row[17],
            listing_type      = row[18],
            status            = row[19],
        )