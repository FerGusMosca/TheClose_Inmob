"""
scripts/insert_properties.py

Carga los JSONs scrapeados directo a Postgres.
Sin lógica de app — solo INSERT crudo.

Uso:
    python scripts/insert_properties.py data/argenprop_smoke.json
    python scripts/insert_properties.py data/zonaprop_smoke.json
    python scripts/insert_properties.py data/argenprop_smoke.json data/zonaprop_smoke.json
"""

import json
import re
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://theclose:theclose123@localhost:5432/theclose_inmob")


# ── Helpers de limpieza ────────────────────────────────────────────────────────

def clean_price(raw: str | None) -> float | None:
    """'159.999' → 159999.0   |   '1.200.000 expensas' → 1200000.0"""
    if not raw:
        return None
    digits = re.sub(r'[^\d]', '', raw.split()[0])
    return float(digits) if digits else None

def clean_expensas(raw: str | None) -> tuple[float | None, str]:
    """'+ $1.160.000 expensas' → (1160000.0, 'ARS')"""
    if not raw:
        return None, 'ARS'
    digits = re.sub(r'[^\d]', '', raw)
    currency = 'USD' if 'USD' in raw.upper() else 'ARS'
    return (float(digits) if digits else None), currency

def safe_int(val) -> int | None:
    try:
        return int(str(val).strip()) if val is not None else None
    except (ValueError, TypeError):
        return None

def safe_float(val) -> float | None:
    try:
        return float(str(val).strip()) if val is not None else None
    except (ValueError, TypeError):
        return None


# ── Carga ──────────────────────────────────────────────────────────────────────

def insert_file(conn, filepath: str):
    with open(filepath, encoding='utf-8') as f:
        data = json.load(f)

    items = data.get('items', [])
    print(f"\n📂 {filepath}  →  {len(items)} items")

    cur = conn.cursor()

    # Lookups
    cur.execute("SELECT id, slug FROM neighborhoods")
    neighborhoods = {row[1]: row[0] for row in cur.fetchall()}

    cur.execute("SELECT id, code FROM sources")
    sources = {row[1]: row[0] for row in cur.fetchall()}

    cur.execute("SELECT id FROM property_types WHERE code = 'departamento'")
    prop_type_id = cur.fetchone()[0]

    cur.execute("SELECT id FROM listing_types WHERE code = 'venta'")
    listing_type_id = cur.fetchone()[0]

    ok = skipped = 0

    for item in items:
        try:
            source_id = sources.get(item.get('source', 'manual'), sources['manual'])

            # Barrio: buscar match en location string
            location = item.get('location') or ''
            neighborhood_id = None
            for slug, nid in neighborhoods.items():
                if slug.lower() in location.lower():
                    neighborhood_id = nid
                    break

            # INSERT property
            cur.execute("""
                INSERT INTO properties
                    (neighborhood_id, property_type_id, address,
                     m2_total, m2_cover, ambientes, dormitorios, banos,
                     title, text_for_embedding)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                neighborhood_id, prop_type_id, location or None,
                safe_float(item.get('m2_total')),
                safe_float(item.get('m2_cover')),
                safe_int(item.get('ambientes')),
                safe_int(item.get('dormitorios')),
                safe_int(item.get('banos')),
                item.get('title'),
                item.get('text_for_embedding'),
            ))
            property_id = cur.fetchone()[0]

            # INSERT listing
            price = clean_price(item.get('price'))
            exp_amount, exp_currency = clean_expensas(item.get('expensas'))

            cur.execute("""
                INSERT INTO listings
                    (property_id, source_id, listing_type_id,
                     portal_id, url, agency,
                     price, currency, expensas, expensas_currency)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (source_id, portal_id) DO NOTHING
            """, (
                property_id, source_id, listing_type_id,
                item.get('portal_id'),
                item.get('url'),
                item.get('agency'),
                price,
                item.get('currency', 'USD'),
                exp_amount,
                exp_currency,
            ))

            # Fila de embedding vacía (vector NULL, se genera después)
            cur.execute("""
                INSERT INTO embeddings (property_id)
                VALUES (%s)
                ON CONFLICT (property_id) DO NOTHING
            """, (property_id,))

            conn.commit()
            ok += 1

        except Exception as e:
            conn.rollback()
            print(f"   ⚠️  portal_id={item.get('portal_id','?')} → {e}")
            skipped += 1

    cur.close()
    print(f"   ✅ OK: {ok}  |  ⚠️  Saltados: {skipped}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/insert_properties.py <archivo.json> [archivo2.json ...]")
        sys.exit(1)

    conn = psycopg2.connect(DATABASE_URL)
    print(f"✅ Conectado a Postgres")

    for filepath in sys.argv[1:]:
        if not Path(filepath).exists():
            print(f"❌ No encontrado: {filepath}")
            continue
        insert_file(conn, filepath)

    conn.close()
    print("\n🏁 Listo.")


if __name__ == "__main__":
    main()