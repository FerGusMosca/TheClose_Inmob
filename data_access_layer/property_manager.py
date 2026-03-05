# data_access_layer/property_manager.py

import psycopg2
from business_entities.property import Property


# ── Column indexes returned by get_properties / get_property_by_id ───────────
_ID_IDX                 = 0
_TITLE_IDX              = 1
_ADDRESS_IDX            = 2
_NEIGHBORHOOD_IDX       = 3
_CITY_IDX               = 4
_PROPERTY_TYPE_IDX      = 5
_AMBIENTES_IDX          = 6
_DORMITORIOS_IDX        = 7
_BANOS_IDX              = 8
_M2_TOTAL_IDX           = 9
_M2_COVER_IDX           = 10
_PRICE_IDX              = 11
_CURRENCY_IDX           = 12
_EXPENSAS_IDX           = 13
_EXPENSAS_CURRENCY_IDX  = 14
_SOURCE_IDX             = 15
_PORTAL_ID_IDX          = 16
_URL_IDX                = 17
_LISTING_TYPE_IDX       = 18
_STATUS_IDX             = 19


def _row_to_property(row) -> Property:
    """Maps a database row to a Property business entity."""
    return Property(
        id                  = row[_ID_IDX],
        title               = row[_TITLE_IDX],
        address             = row[_ADDRESS_IDX],
        neighborhood        = row[_NEIGHBORHOOD_IDX],
        city                = row[_CITY_IDX],
        property_type       = row[_PROPERTY_TYPE_IDX],
        ambientes           = row[_AMBIENTES_IDX],
        dormitorios         = row[_DORMITORIOS_IDX],
        banos               = row[_BANOS_IDX],
        m2_total            = float(row[_M2_TOTAL_IDX])  if row[_M2_TOTAL_IDX]  else None,
        m2_cover            = float(row[_M2_COVER_IDX])  if row[_M2_COVER_IDX]  else None,
        price               = float(row[_PRICE_IDX])     if row[_PRICE_IDX]     else None,
        currency            = row[_CURRENCY_IDX],
        expensas            = float(row[_EXPENSAS_IDX])  if row[_EXPENSAS_IDX]  else None,
        expensas_currency   = row[_EXPENSAS_CURRENCY_IDX],
        source              = row[_SOURCE_IDX],
        portal_id           = row[_PORTAL_ID_IDX],
        url                 = row[_URL_IDX],
        listing_type        = row[_LISTING_TYPE_IDX],
        status              = row[_STATUS_IDX],
    )


class PropertyManager:

    def __init__(self, database_url: str):
        self.database_url = database_url

    def _connect(self):
        return psycopg2.connect(self.database_url)

    def get_properties(
        self,
        neighborhood:   str   | None = None,
        ambientes:      int   | None = None,
        price_min:      float | None = None,
        price_max:      float | None = None,
        source:         str   | None = None,
        limit:          int          = 50,
        offset:         int          = 0,
    ) -> list[Property]:
        """Calls get_properties stored function with explicit type casts to avoid ambiguity."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT * FROM get_properties(
                        %s::VARCHAR,
                        %s::SMALLINT,
                        %s::NUMERIC,
                        %s::NUMERIC,
                        %s::VARCHAR,
                        %s::INT,
                        %s::INT
                    )""",
                    (neighborhood, ambientes, price_min, price_max, source, limit, offset)
                )
                return [_row_to_property(row) for row in cur.fetchall()]

    def get_property_by_id(self, property_id: int) -> Property | None:
        """Calls get_property_by_id stored function."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM get_property_by_id(%s::INT)",
                    (property_id,)
                )
                row = cur.fetchone()
                return _row_to_property(row) if row else None

    def get_neighborhoods(self) -> list[dict]:
        """Calls get_neighborhoods stored function. Used to populate filter dropdown."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM get_neighborhoods()")
                return [{"slug": row[0], "name": row[1]} for row in cur.fetchall()]

    def get_stats(self) -> dict:
        """Calls get_property_stats stored function. Used by the dashboard."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM get_property_stats()")
                row = cur.fetchone()
                if not row:
                    return {}
                return {
                    "total_properties": row[0],
                    "total_listings":   row[1],
                    "avg_price":        float(row[2]) if row[2] else None,
                    "top_neighborhood": row[3],
                }