# common/scrapers/zonaprop_scraper.py
"""
Scraper for Zonaprop listing pages.
Uses undetected_chromedriver to bypass Cloudflare Turnstile.
Returns a list of Property business entities.
"""

import logging
import re
import time
from typing import Optional

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.common.exceptions import SessionNotCreatedException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from business_entities.property import Property
from common.util.scrappers.argenprop_scraper import ArgenpropScraper

# ── Card selectors ────────────────────────────────────────────────────────────
_CARD_SELECTORS = [
    "div[data-qa='posting PROPERTY']",
    "article[class*='posting']",
    "li[class*='posting']",
    "div[class*='posting']",
    "[data-qa*='posting-card']",
    "[data-testid*='posting']",
    "article.card",
]

_WAIT_SELECTOR = (
    "[data-qa*='posting'], [data-testid*='posting'], "
    "article[class*='posting'], div[class*='posting'], "
    "#g-recaptcha, .cf-browser-verification"
)

_CF_PATTERNS = [
    r"cloudflare", r"cf-browser-verification", r"Checking your browser",
    r"Attention Required", r"verify you are a human", r"challenge-platform",
    r"/cdn-cgi/challenge", r"cf-error", r"robot|bot detected|acceso denegado",
]

log = logging.getLogger(__name__)


class ZonapropScraper:
    """
    Scrapes Zonaprop listing pages for a given neighborhood.
    Uses undetected_chromedriver to bypass Cloudflare protection.
    Returns a list of Property business entities ready for persistence.
    """

    BASE_URL_TEMPLATE = "https://www.zonaprop.com.ar/departamentos-venta-{neighborhood}.html"

    def __init__(self, headless: bool = True, page_wait: float = 2.0):
        self.headless  = headless
        self.page_wait = page_wait

    # ── Public interface ──────────────────────────────────────────────────────

    def scrape(self, neighborhood_slug: str, max_pages: int = 5) -> list[Property]:
        """
        Scrapes Zonaprop for the given neighborhood.
        Returns a deduplicated list of Property entities.
        """
        base_url = self.BASE_URL_TEMPLATE.format(neighborhood=neighborhood_slug)
        log.info("ZonapropScraper.scrape | url=%s max_pages=%d", base_url, max_pages)

        driver = self._build_driver()
        try:
            return self._scrape_pages(driver, base_url, neighborhood_slug, max_pages)
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    # ── Driver ────────────────────────────────────────────────────────────────

    def _build_driver(self):
        """Builds undetected Chrome driver with automatic version detection."""
        def _make_opts() -> uc.ChromeOptions:
            opts = uc.ChromeOptions()
            if self.headless:
                opts.add_argument("--headless=new")
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--window-size=1366,900")
            opts.add_argument("--lang=es-AR,es")
            opts.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            return opts

        chrome_version = self._detect_chrome_version()
        log.info("ZonapropScraper | chrome_version=%s", chrome_version or "auto")

        try:
            driver = (uc.Chrome(options=_make_opts(), version_main=chrome_version)
                      if chrome_version else uc.Chrome(options=_make_opts()))
        except SessionNotCreatedException as e:
            m = re.search(r"Current browser version is (\d+)", str(e))
            if not m:
                raise
            fallback_version = int(m.group(1))
            log.warning("ZonapropScraper | retrying with version_main=%d", fallback_version)
            driver = uc.Chrome(options=_make_opts(), version_main=fallback_version)

        driver.set_window_size(1366, 900)

        # Simulate Google referrer
        try:
            driver.execute_cdp_cmd(
                "Network.setExtraHTTPHeaders",
                {"headers": {"Referer": "https://www.google.com/"}}
            )
        except Exception:
            pass

        return driver

    @staticmethod
    def _detect_chrome_version() -> Optional[int]:
        """Detects installed Chrome major version to avoid driver mismatch."""
        import subprocess
        import shutil
        from pathlib import Path

        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
        ]
        which = shutil.which("google-chrome") or shutil.which("chromium") or ""
        if which:
            candidates.append(which)

        for candidate in candidates:
            if candidate and Path(candidate).exists():
                try:
                    out = subprocess.check_output(
                        [candidate, "--version"], stderr=subprocess.DEVNULL, timeout=5
                    ).decode()
                    m = re.search(r"(\d+)\.\d+\.\d+", out)
                    if m:
                        return int(m.group(1))
                except Exception:
                    pass
        return None

    # ── Pagination ────────────────────────────────────────────────────────────

    def _build_page_url(self, base_url: str, page: int) -> str:
        """Page 1 → original URL. Page N → inserts -pagina-N before .html."""
        if page == 1:
            return base_url
        clean = re.sub(r"(-pagina-\d+)?\.html$", "", base_url)
        return f"{clean}-pagina-{page}.html"

    # ── Block detection ───────────────────────────────────────────────────────

    def _is_blocked(self, html: str) -> bool:
        for pat in _CF_PATTERNS:
            if re.search(pat, html, re.IGNORECASE):
                return True
        return len(html) < 5_000

    # ── Page loading ──────────────────────────────────────────────────────────

    def _load_page(self, driver, url: str, page_num: int) -> str:
        """Navigates to URL, accepts cookies, scrolls to trigger lazy load."""
        driver.get(url)

        try:
            WebDriverWait(driver, 14).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, _WAIT_SELECTOR))
            )
        except TimeoutException:
            log.warning("ZonapropScraper | wait timeout page=%d", page_num)

        # Accept cookie popup if present
        for xpath in [
            "//button[contains(.,'Acept')]",
            "//button[contains(.,'Entendido')]",
            "//button[contains(.,'continuar')]",
        ]:
            try:
                btns = driver.find_elements(By.XPATH, xpath)
                if btns and btns[0].is_displayed():
                    btns[0].click()
                    break
            except Exception:
                pass

        # Scroll to trigger lazy-load images and cards
        try:
            for _ in range(4):
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(0.35)
        except Exception:
            pass

        return driver.page_source or ""

    # ── Page scraping loop ────────────────────────────────────────────────────

    def _scrape_pages(
        self,
        driver,
        base_url: str,
        neighborhood_slug: str,
        max_pages: int,
    ) -> list[Property]:
        all_properties: list[Property] = []
        seen_keys: set                 = set()

        for page_num in range(1, max_pages + 1):
            url = self._build_page_url(base_url, page_num)
            log.info("ZonapropScraper | page=%d url=%s", page_num, url)

            html    = self._load_page(driver, url, page_num)
            blocked = self._is_blocked(html)

            if blocked:
                log.warning("ZonapropScraper | blocked on page=%d", page_num)

            soup      = BeautifulSoup(html, "html.parser")
            raw_items = self._parse_cards(soup, neighborhood_slug)

            new_items = []
            for p in raw_items:
                key = f"zp:{p.portal_id or p.url}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    new_items.append(p)

            all_properties.extend(new_items)
            log.info("ZonapropScraper | page=%d new=%d total=%d",
                     page_num, len(new_items), len(all_properties))

            if (blocked and not new_items) or not new_items:
                log.info("ZonapropScraper | stopping — no new items")
                break

            if page_num < max_pages:
                time.sleep(self.page_wait)

        return all_properties

    # ── Card parsing ──────────────────────────────────────────────────────────

    def _find_cards(self, soup: BeautifulSoup) -> list:
        for sel in _CARD_SELECTORS:
            cards = soup.select(sel)
            if cards:
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
                log.debug("ZonapropScraper | card parse error: %s", e)

        return results

    def _parse_card(self, card, neighborhood_slug: str) -> Optional[Property]:
        # URL
        a_tag = card.select_one("a[href]")
        if not a_tag:
            return None

        href = a_tag.get("href", "")
        url  = href if href.startswith("http") else f"https://www.zonaprop.com.ar{href}"

        # Portal ID
        pid_m     = re.search(r"-(\d{6,})\.", url)
        portal_id = pid_m.group(1) if pid_m else None

        # Title
        title_el = card.select_one("[data-qa='POSTING_CARD_DESCRIPTION'], h2, h3")
        title    = self._text(title_el) or None

        # Price
        price_el  = card.select_one("[data-qa='POSTING_CARD_PRICE'], [class*='price']")
        price_raw = self._text(price_el)
        currency  = ("USD" if re.search(r"USD|U\$S", price_raw)
                     else "ARS" if "$" in price_raw else "USD")
        price_str = re.sub(r"(USD|U\$S|ARS|\$|\s)", "", price_raw).strip() or None
        price_str = re.sub(r"\.", "", price_str) if price_str else None
        price     = float(price_str) if price_str and price_str.isdigit() else None

        # Expensas
        exp_el  = card.select_one("[data-qa='POSTING_CARD_EXPENSES'], [class*='expense']")
        exp_str = re.sub(r"[^\d]", "", self._text(exp_el))
        expensas = float(exp_str) if exp_str else None

        # Location
        loc_el   = card.select_one("[data-qa='POSTING_CARD_LOCATION'], [class*='location'], [class*='address']")
        location = self._text(loc_el) or None

        # Features
        feat_el   = card.select_one("[data-qa='POSTING_CARD_FEATURES'], [class*='feature'], [class*='main-features']")
        feat_text = self._text(feat_el)

        ambientes   = self._re_first(r"(\d+)\s*amb",   feat_text) or None
        dormitorios = self._re_first(r"(\d+)\s*dorm",  feat_text) or None
        banos       = self._re_first(r"(\d+)\s*ba[ñn]", feat_text) or None
        m2_total    = (self._re_first(r"(\d[\d\.]+)\s*m²?\s*tot", feat_text)
                       or self._re_first(r"(\d[\d\.]+)\s*m²", feat_text) or None)
        m2_cover    = self._re_first(r"(\d[\d\.]+)\s*m²?\s*cub", feat_text) or None

        # Agency
        ag_el  = card.select_one("[data-qa='POSTING_CARD_PUBLISHER'], [class*='agency'], [class*='publisher']")
        agency = self._text(ag_el) or None

        text_for_embedding = ArgenpropScraper._build_embedding_text(
            title=title, price=price, currency=currency,
            expensas=expensas, ambientes=ambientes, dormitorios=dormitorios,
            banos=banos, m2_total=m2_total, m2_cover=m2_cover,
            location=location, agency=agency,
            neighborhood_slug=neighborhood_slug,
        )

        return Property(
            id=0,
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
            source="zonaprop",
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


