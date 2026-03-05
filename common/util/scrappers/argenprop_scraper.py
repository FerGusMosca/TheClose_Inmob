# common/scrapers/argenprop_scraper.py
import logging, re, time
from typing import Optional
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from business_entities.property import Property

_CARD_SELECTORS = ["div.listing__item","div.postings-container > div","li.listing__item","article.card"]
_WAIT_SELECTOR  = ", ".join(["div.listing__item","div.card","article.card","#g-recaptcha",".cf-browser-verification"])
_CF_STRONG      = [r"cf-browser-verification",r"Checking your browser",r"Attention Required",r"verify you are a human",r"/cdn-cgi/challenge",r"cf-error",r"acceso denegado|access denied",r"robot|bot detected"]
_CF_WEAK        = [r"cloudflare",r"challenge-platform"]

log = logging.getLogger(__name__)


class ArgenpropScraper:
    BASE_URL_TEMPLATE = "https://www.argenprop.com/departamento-venta-barrio-{neighborhood}"

    def __init__(self, headless: bool = True, page_wait: float = 2.0):
        self.headless  = headless
        self.page_wait = page_wait

    def scrape(self, neighborhood_slug: str, max_pages: int = 5) -> list[Property]:
        base_url = self.BASE_URL_TEMPLATE.format(neighborhood=neighborhood_slug)
        log.info("ArgenpropScraper.scrape | url=%s max_pages=%d", base_url, max_pages)
        driver = self._build_driver()
        try:
            return self._scrape_pages(driver, base_url, neighborhood_slug, max_pages)
        finally:
            try: driver.quit()
            except: pass

    def _build_driver(self):
        opts = Options()
        if self.headless: opts.add_argument("--headless=new")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1440,900")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--lang=es-AR,es")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        return webdriver.Chrome(options=opts)

    def _detect_next_url(self, soup):
        next_a = soup.select_one("a[rel='next'], a.pagination__page--next, a[aria-label='Siguiente'], li.pagination__item--next > a")
        if not next_a: return None
        href = next_a.get("href", "")
        return href if href.startswith("http") else f"https://www.argenprop.com{href}"

    def _is_blocked(self, html):
        for p in _CF_STRONG:
            if re.search(p, html, re.IGNORECASE): return True
        if sum(1 for p in _CF_WEAK if re.search(p, html, re.IGNORECASE)) >= 2: return True
        return len(html) < 5_000

    def _scrape_pages(self, driver, base_url, neighborhood_slug, max_pages):
        all_props, seen_ids, next_url = [], set(), base_url
        for page_num in range(1, max_pages + 1):
            driver.get(next_url)
            try: WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.CSS_SELECTOR, _WAIT_SELECTOR)))
            except TimeoutException: log.warning("ArgenpropScraper | timeout page=%d", page_num)
            time.sleep(1.5)
            html = driver.page_source or ""
            if self._is_blocked(html): log.warning("ArgenpropScraper | blocked on page=%d", page_num)
            soup      = BeautifulSoup(html, "html.parser")
            new_items = [p for p in self._parse_cards(soup, neighborhood_slug) if p.portal_id not in seen_ids]
            for p in new_items: seen_ids.add(p.portal_id)
            all_props.extend(new_items)
            log.info("ArgenpropScraper | page=%d new=%d total=%d", page_num, len(new_items), len(all_props))
            next_url = self._detect_next_url(soup) or ""
            if not next_url or not new_items: break
            if page_num < max_pages: time.sleep(self.page_wait)
        return all_props

    def _find_cards(self, soup):
        for sel in _CARD_SELECTORS:
            cards = soup.select(sel)
            if len(cards) >= 3: return cards
        return []

    def _parse_cards(self, soup, neighborhood_slug):
        results, seen_urls = [], set()
        for card in self._find_cards(soup):
            try:
                prop = self._parse_card(card, neighborhood_slug)
                if prop and prop.url and prop.url not in seen_urls:
                    seen_urls.add(prop.url)
                    results.append(prop)
            except Exception as e:
                log.debug("card parse error: %s", e)
        return results

    def _parse_card(self, card, neighborhood_slug):
        a_tag = card.select_one("a[href*='argenprop.com']") or card.select_one("a[href^='/']")
        if not a_tag: return None
        href = a_tag.get("href", "")
        url  = href if href.startswith("http") else f"https://www.argenprop.com{href}"

        portal_id = card.get("data-id") or card.get("data-posting-id")
        if not portal_id:
            m = re.search(r"-(\d{6,})(?:\.html|$)", url)
            portal_id = m.group(1) if m else None

        title_el = card.select_one(".card__title") or card.select_one("h2, h3")
        title    = self._text(title_el) or None

        # ── Price from dedicated element only ─────────────────────────────────
        price, currency = self._parse_price(card.select_one(".card__price, .price"))

        # ── Expensas from dedicated element only ──────────────────────────────
        expensas = self._parse_expensas(card.select_one(".card__expenses, .expenses"))

        loc_el   = card.select_one(".card__address, .posting-location")
        location = self._text(loc_el) or None

        feat_el     = card.select_one(".card__main-features, .card__features, ul.card-tags")
        feat_items  = [self._text(li) for li in (feat_el.select("li") if feat_el else [])]
        feat_joined = " | ".join(feat_items) or self._text(feat_el)

        ambientes   = self._re_first(r"(\d+)\s*amb",              feat_joined) or None
        dormitorios = self._re_first(r"(\d+)\s*dorm",             feat_joined) or None
        banos       = self._re_first(r"(\d+)\s*ba[ñn]",          feat_joined) or None
        m2_total    = (self._re_first(r"(\d[\d\.]+)\s*m²?\s*tot", feat_joined)
                       or self._re_first(r"(\d[\d\.]+)\s*m²",     feat_joined) or None)
        m2_cover    = self._re_first(r"(\d[\d\.]+)\s*m²?\s*cub",  feat_joined) or None

        ag_el  = card.select_one(".card__publisher, .publisher-name, .posting-contact")
        agency = self._text(ag_el) or None

        return Property(
            id=0, title=title, address=location, neighborhood=neighborhood_slug,
            city="Buenos Aires", property_type="departamento",
            ambientes=int(ambientes) if ambientes else None,
            dormitorios=int(dormitorios) if dormitorios else None,
            banos=int(banos) if banos else None,
            m2_total=float(m2_total) if m2_total else None,
            m2_cover=float(m2_cover) if m2_cover else None,
            price=price, currency=currency, expensas=expensas, expensas_currency="ARS",
            source="argenprop", portal_id=portal_id, url=url,
            listing_type="venta", status="active",
            text_for_embedding=self._build_embedding_text(
                title=title, price=price, currency=currency, expensas=expensas,
                ambientes=ambientes, dormitorios=dormitorios, banos=banos,
                m2_total=m2_total, m2_cover=m2_cover, location=location,
                agency=agency, neighborhood_slug=neighborhood_slug,
            ),
        )

    # ── Price parsing — first number only, isolated from expensas ─────────────

    @staticmethod
    def _parse_price(el) -> tuple[Optional[float], str]:
        """
        Reads only the price element text and extracts the FIRST number found.
        This prevents expensas from leaking into the price when both appear
        in the same text node.
        """
        if not el: return None, "USD"
        raw = ArgenpropScraper._text(el)
        if not raw: return None, "USD"

        currency = "USD" if re.search(r"USD|U\$S|u\$s", raw, re.IGNORECASE) else \
                   "ARS" if re.search(r"ARS|\$", raw) else "USD"

        # Extract FIRST number sequence (stops at first non-numeric char after digits)
        m = re.search(r"([\d][\d\.]*\d|\d)", raw)
        if not m: return None, currency

        # Remove thousand-separator dots (dot followed by exactly 3 digits)
        num_str = re.sub(r"\.(?=\d{3}(\D|$))", "", m.group(1))
        num_str = num_str.replace(".", "").replace(",", "")

        try:
            val = float(num_str)
            # Sanity check: real estate prices in Argentina are < 50M USD
            if val > 50_000_000:
                log.warning("ArgenpropScraper | suspicious price=%s raw=%r — skipping", val, raw)
                return None, currency
            return val, currency
        except ValueError:
            return None, currency

    @staticmethod
    def _parse_expensas(el) -> Optional[float]:
        if not el: return None
        raw = ArgenpropScraper._text(el)
        if not raw: return None
        m = re.search(r"([\d][\d\.]*\d|\d)", raw)
        if not m: return None
        num_str = re.sub(r"\.(?=\d{3}(\D|$))", "", m.group(1))
        num_str = num_str.replace(".", "").replace(",", "")
        try: return float(num_str)
        except ValueError: return None

    @staticmethod
    def _text(el) -> str:
        return re.sub(r"\s+", " ", el.get_text(strip=True)).strip() if el else ""

    @staticmethod
    def _re_first(pattern: str, text: str) -> str:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _build_embedding_text(title, price, currency, expensas, ambientes, dormitorios,
                               banos, m2_total, m2_cover, location, agency, neighborhood_slug) -> str:
        parts = [f"Departamento en venta en {neighborhood_slug.replace('-', ' ')}, Buenos Aires."]
        if title and len(title) > 10: parts.append(title.strip(".") + ".")
        if price:    parts.append(f"Precio: {currency} {price}.")
        if expensas: parts.append(f"Expensas: ARS {expensas}.")
        amb = []
        if ambientes:   amb.append(f"{ambientes} ambientes")
        if dormitorios: amb.append(f"{dormitorios} dormitorios")
        if banos:       amb.append(f"{banos} baños")
        if amb: parts.append("Distribución: " + ", ".join(amb) + ".")
        m2 = []
        if m2_total: m2.append(f"{m2_total} m² totales")
        if m2_cover and m2_cover != m2_total: m2.append(f"{m2_cover} m² cubiertos")
        if m2: parts.append("Superficie: " + ", ".join(m2) + ".")
        if location: parts.append(f"Ubicación: {location}.")
        if agency:   parts.append(f"Inmobiliaria: {agency}.")
        return " ".join(parts)