# common/scrapers/argenprop_scraper.py
"""
Scraper for Argenprop listing pages.
Uses Selenium + BeautifulSoup to extract property listings.
Returns a list of Property business entities.
"""

import logging
import re
import time
from typing import Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from business_entities.property import Property


# ── Card selectors ────────────────────────────────────────────────────────────
_CARD_SELECTORS = [
    "div.listing__item",
    "div.postings-container > div",
    "li.listing__item",
    "article.card",
]

_WAIT_SELECTOR = ", ".join([
    "div.listing__item",
    "div.card",
    "article.card",
    "#g-recaptcha",
    ".cf-browser-verification",
])

_CF_STRONG_PATTERNS = [
    r"cf-browser-verification",
    r"Checking your browser",
    r"Attention Required",
    r"verify you are a human",
    r"/cdn-cgi/challenge",
    r"cf-error",
    r"acceso denegado|access denied",
    r"robot|bot detected",
]

_CF_WEAK_PATTERNS = [
    r"cloudflare",
    r"challenge-platform",
]

log = logging.getLogger(__name__)


class ArgenpropScraper:
    """
    Scrapes Argenprop listing pages for a given neighborhood.
    Returns a list of Property business entities ready for persistence.
    """

    BASE_URL_TEMPLATE = "https://www.argenprop.com/departamento-venta-barrio-{neighborhood}"

    def __init__(self, headless: bool = True, page_wait: float = 2.0):
        self.headless   = headless
        self.page_wait  = page_wait

    # ── Public interface ──────────────────────────────────────────────────────

    def scrape(self, neighborhood_slug: str, max_pages: int = 5) -> list[Property]:
        """
        Scrapes Argenprop for the given neighborhood.
        Returns a deduplicated list of Property entities.
        """
        base_url = self.BASE_URL_TEMPLATE.format(neighborhood=neighborhood_slug)
        log.info("ArgenpropScraper.scrape | url=%s max_pages=%d", base_url, max_pages)

        driver = self._build_driver()
        try:
            return self._scrape_pages(driver, base_url, neighborhood_slug, max_pages)
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    # ── Driver ────────────────────────────────────────────────────────────────

    def _build_driver(self) -> webdriver.Chrome:
        opts = Options()
        if self.headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1440,900")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--lang=es-AR,es")
        opts.add_argument("--disable-extensions")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        return webdriver.Chrome(options=opts)

    # ── Pagination ────────────────────────────────────────────────────────────

    def _build_page_url(self, base_url: str, page: int) -> str:
        """Page 1 → original URL. Page N → appends ?pagina=N."""
        if page == 1:
            return base_url
        clean = re.sub(r"[?&]pagina=\d+", "", base_url)
        sep   = "&" if "?" in clean else "?"
        return f"{clean}{sep}pagina={page}"

    def _detect_next_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extracts the next page URL from pagination links."""
        next_a = soup.select_one(
            "a[rel='next'], a.pagination__page--next, "
            "a[aria-label='Siguiente'], li.pagination__item--next > a"
        )
        if not next_a:
            return None
        href = next_a.get("href", "")
        return href if href.startswith("http") else f"https://www.argenprop.com{href}"

    # ── Block detection ───────────────────────────────────────────────────────

    def _is_blocked(self, html: str) -> bool:
        for pat in _CF_STRONG_PATTERNS:
            if re.search(pat, html, re.IGNORECASE):
                return True
        weak_hits = sum(1 for p in _CF_WEAK_PATTERNS if re.search(p, html, re.IGNORECASE))
        if weak_hits >= 2:
            return True
        if len(html) < 5_000:
            return True
        return False

    # ── Page scraping loop ────────────────────────────────────────────────────

    def _scrape_pages(
        self,
        driver: webdriver.Chrome,
        base_url: str,
        neighborhood_slug: str,
        max_pages: int,
    ) -> list[Property]:
        all_properties: list[Property] = []
        seen_portal_ids: set           = set()
        next_url                       = base_url

        for page_num in range(1, max_pages + 1):
            log.info("ArgenpropScraper | page=%d url=%s", page_num, next_url)

            driver.get(next_url)
            try:
                WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, _WAIT_SELECTOR))
                )
            except TimeoutException:
                log.warning("ArgenpropScraper | wait timeout page=%d", page_num)

            time.sleep(1.5)
            html = driver.page_source or ""

            if self._is_blocked(html):
                log.warning("ArgenpropScraper | blocked on page=%d", page_num)

            soup       = BeautifulSoup(html, "html.parser")
            raw_items  = self._parse_cards(soup, neighborhood_slug)
            new_items  = [p for p in raw_items if p.portal_id not in seen_portal_ids]

            for p in new_items:
                seen_portal_ids.add(p.portal_id)
            all_properties.extend(new_items)

            log.info("ArgenpropScraper | page=%d new=%d total=%d",
                     page_num, len(new_items), len(all_properties))

            next_url = self._detect_next_url(soup) or ""
            if not next_url or not new_items:
                log.info("ArgenpropScraper | stopping — no more pages")
                break

            if page_num < max_pages:
                time.sleep(self.page_wait)

        return all_properties

    # ── Card parsing ──────────────────────────────────────────────────────────

    def _find_cards(self, soup: BeautifulSoup) -> list:
        for sel in _CARD_SELECTORS:
            cards = soup.select(sel)
            if len(cards) >= 3:
                return cards
        return []

    def _parse_cards(self, soup: BeautifulSoup, neighborhood_slug: str) -> list[Property]:
        results: list[Property] = []
        seen_urls: set          = set()

        for card in self._find_cards(soup):
            try:
                prop = self._parse_card(card, neighborhood_slug)
                if prop and prop.url and prop.url not in seen_urls:
                    seen_urls.add(prop.url)
                    results.append(prop)
            except Exception as e:
                log.debug("ArgenpropScraper | card parse error: %s", e)

        return results

    def _parse_card(self, card, neighborhood_slug: str) -> Optional[Property]:
        # URL
        a_tag = (
            card.select_one("a[href*='argenprop.com']")
            or card.select_one("a[href^='/']")
        )
        if not a_tag:
            return None

        href = a_tag.get("href", "")
        url  = href if href.startswith("http") else f"https://www.argenprop.com{href}"

        # Portal ID
        portal_id = card.get("data-id") or card.get("data-posting-id")
        if not portal_id:
            m = re.search(r"-(\d{6,})(?:\.html|$)", url)
            portal_id = m.group(1) if m else None

        # Title
        title_el = card.select_one(".card__title") or card.select_one("h2, h3")
        title    = self._text(title_el) or None

        # Price
        price_el  = card.select_one(".card__price, .price")
        price_raw = self._text(price_el)
        currency  = ("USD" if re.search(r"USD|U\$S|u\$s", price_raw)
                     else "ARS" if "$" in price_raw else "USD")
        price_str = re.sub(r"[^\d\.]", "", price_raw) or None
        price     = float(re.sub(r"\.", "", price_str)) if price_str else None

        # Expensas
        exp_el    = card.select_one(".card__expenses, .expenses")
        exp_raw   = self._text(exp_el)
        exp_str   = re.sub(r"[^\d]", "", exp_raw)
        expensas  = float(exp_str) if exp_str else None

        # Location
        loc_el   = card.select_one(".card__address, .posting-location")
        location = self._text(loc_el) or None

        # Features
        feat_el     = card.select_one(".card__main-features, .card__features, ul.card-tags")
        feat_items  = [self._text(li) for li in (feat_el.select("li") if feat_el else [])]
        feat_joined = " | ".join(feat_items) or self._text(feat_el)

        ambientes   = self._re_first(r"(\d+)\s*amb",             feat_joined) or None
        dormitorios = self._re_first(r"(\d+)\s*dorm",            feat_joined) or None
        banos       = self._re_first(r"(\d+)\s*ba[ñn]",         feat_joined) or None
        m2_total    = (self._re_first(r"(\d[\d\.]+)\s*m²?\s*tot", feat_joined)
                       or self._re_first(r"(\d[\d\.]+)\s*m²",    feat_joined) or None)
        m2_cover    = self._re_first(r"(\d[\d\.]+)\s*m²?\s*cub", feat_joined) or None

        # Agency
        ag_el  = card.select_one(".card__publisher, .publisher-name, .posting-contact")
        agency = self._text(ag_el) or None

        text_for_embedding = self._build_embedding_text(
            title=title, price=price, currency=currency,
            expensas=expensas, ambientes=ambientes, dormitorios=dormitorios,
            banos=banos, m2_total=m2_total, m2_cover=m2_cover,
            location=location, agency=agency,
            neighborhood_slug=neighborhood_slug,
        )

        return Property(
            id=0,  # assigned by DB on insert
            title=title,
            address=location,
            neighborhood=neighborhood_slug,
            city="Buenos Aires",
            property_type="departamento",
            ambientes=int(ambientes) if ambientes else None,
            dormitorios=int(dormitorios) if dormitorios else None,
            banos=int(banos) if banos else None,
            m2_total=float(m2_total) if m2_total else None,
            m2_cover=float(m2_cover) if m2_cover else None,
            price=price,
            currency=currency,
            expensas=expensas,
            expensas_currency="ARS",
            source="argenprop",
            portal_id=portal_id,
            url=url,
            listing_type="venta",
            status="active",
            text_for_embedding=text_for_embedding,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _text(el) -> str:
        return re.sub(r"\s+", " ", el.get_text(strip=True)).strip() if el else ""

    @staticmethod
    def _re_first(pattern: str, text: str) -> str:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _build_embedding_text(
        title, price, currency, expensas, ambientes, dormitorios,
        banos, m2_total, m2_cover, location, agency, neighborhood_slug,
    ) -> str:
        """Builds a natural language narrative for vector embedding."""
        parts = [f"Departamento en venta en {neighborhood_slug.replace('-', ' ')}, Buenos Aires."]

        if title and len(title) > 10:
            parts.append(title.strip(".") + ".")
        if price and currency:
            parts.append(f"Precio: {currency} {price}.")
        if expensas:
            parts.append(f"Expensas: ARS {expensas}.")

        amb_parts = []
        if ambientes:   amb_parts.append(f"{ambientes} ambientes")
        if dormitorios: amb_parts.append(f"{dormitorios} dormitorios")
        if banos:       amb_parts.append(f"{banos} baños")
        if amb_parts:
            parts.append("Distribución: " + ", ".join(amb_parts) + ".")

        m2_parts = []
        if m2_total: m2_parts.append(f"{m2_total} m² totales")
        if m2_cover and m2_cover != m2_total:
            m2_parts.append(f"{m2_cover} m² cubiertos")
        if m2_parts:
            parts.append("Superficie: " + ", ".join(m2_parts) + ".")

        if location: parts.append(f"Ubicación: {location}.")
        if agency:   parts.append(f"Inmobiliaria: {agency}.")

        return " ".join(parts)