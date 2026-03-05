# common/pipeline/pipeline_runner.py
"""
Orchestrates the data pipeline: scrape → insert → embed.
Each step runs in a background thread and streams logs via SSE queues.
Uses scrapers from common/scrapers and PropertyManager for all DB access.
"""

import json
import logging
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from openai import OpenAI
from common.util.scrappers.argenprop_scraper import ArgenpropScraper
from common.util.scrappers.zonaprop_scraper import ZonapropScraper
from data_access_layer.property_manager import PropertyManager

log = logging.getLogger(__name__)


class StepStatus(str, Enum):
    IDLE    = "idle"
    RUNNING = "running"
    DONE    = "done"
    ERROR   = "error"


@dataclass
class StepState:
    status:     StepStatus   = StepStatus.IDLE
    started_at: Optional[str] = None
    ended_at:   Optional[str] = None
    message:    str           = ""
    count:      int           = 0


class PipelineRunner:
    """
    Singleton-style runner — one active job per step at a time.
    Subscribers receive SSE messages via per-client queues.
    """

    def __init__(self, database_url: str, openai_api_key: str):
        self.database_url   = database_url
        self.openai_api_key = openai_api_key

        self.states: dict[str, StepState] = {
            "scrape_argenprop": StepState(),
            "scrape_zonaprop":  StepState(),
            "insert":           StepState(),
            "embed":            StepState(),
        }

        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()

    # ── SSE pub/sub ───────────────────────────────────────────────────────────

    def subscribe(self) -> queue.Queue:
        q = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _publish(self, event: str, data: dict):
        msg = f"event: {event}\ndata: {json.dumps(data)}\n\n"
        with self._lock:
            for q in self._subscribers:
                try:
                    q.put_nowait(msg)
                except Exception:
                    pass

    def _log(self, step: str, line: str):
        log.info("[%s] %s", step, line)
        self._publish("log", {
            "step": step,
            "line": line,
            "ts":   datetime.now().strftime("%H:%M:%S"),
        })

    def _set_state(self, step: str, **kwargs):
        state = self.states[step]
        for k, v in kwargs.items():
            setattr(state, k, v)
        self._publish("state", {
            "step":       step,
            "status":     str(state.status),
            "started_at": state.started_at,
            "ended_at":   state.ended_at,
            "message":    state.message,
            "count":      state.count,
        })

    # ── Thread launcher ───────────────────────────────────────────────────────

    def _launch(self, step: str, fn, *args) -> bool:
        """Launches fn in a background thread. Returns False if already running."""
        if self.states[step].status == StepStatus.RUNNING:
            return False

        self._set_state(step,
            status     = StepStatus.RUNNING,
            started_at = datetime.now().isoformat(),
            ended_at   = None,
            message    = "Running...",
            count      = 0,
        )

        def _run():
            try:
                fn(*args)
                self._set_state(step,
                    status   = StepStatus.DONE,
                    ended_at = datetime.now().isoformat(),
                    message  = "Completed",
                )
            except Exception as e:
                log.exception("[%s] unhandled error", step)
                self._set_state(step,
                    status   = StepStatus.ERROR,
                    ended_at = datetime.now().isoformat(),
                    message  = str(e),
                )
                self._log(step, f"ERROR: {e}")

        threading.Thread(target=_run, daemon=True).start()
        return True

    # ── STEP 1: Scrape ────────────────────────────────────────────────────────

    def run_scrape(self, portal: str, neighborhood_slug: str, max_pages: int) -> bool:
        """
        Scrapes the given portal for properties in neighborhood_slug.
        Stores scraped Property list in self._last_scraped[portal].
        """
        step = f"scrape_{portal}"

        # Storage for scraped results (picked up by run_insert)
        if not hasattr(self, "_last_scraped"):
            self._last_scraped: dict = {}

        def _scrape():
            self._log(step, f"Starting {portal} — neighborhood={neighborhood_slug} pages={max_pages}")

            if portal == "argenprop":

                scraper = ArgenpropScraper(headless=True)
            else:

                scraper = ZonapropScraper(headless=True)

            properties = scraper.scrape(neighborhood_slug, max_pages=max_pages)
            self._last_scraped[portal] = properties

            self._set_state(step, count=len(properties),
                            message=f"{len(properties)} properties scraped")
            self._log(step, f"Done — {len(properties)} properties")

        return self._launch(step, _scrape)

    # ── STEP 2: Insert ────────────────────────────────────────────────────────

    def run_insert(self, portals: list[str]) -> bool:
        """
        Inserts scraped properties into the database using PropertyManager.
        Uses self._last_scraped if available, otherwise reports missing data.
        """
        step = "insert"

        def _insert():
            manager   = PropertyManager(self.database_url)
            total_ok  = 0
            total_skip = 0

            for portal in portals:
                scraped = getattr(self, "_last_scraped", {}).get(portal, [])

                if not scraped:
                    self._log(step, f"No scraped data for {portal} — run scrape first")
                    continue

                self._log(step, f"Inserting {portal} — {len(scraped)} properties")
                ok = skip = 0

                for prop in scraped:
                    try:
                        result = manager.persist_property(prop)
                        if result is not None:
                            ok += 1
                        else:
                            skip += 1
                    except Exception as e:
                        skip += 1
                        self._log(step, f"  skip portal_id={prop.portal_id} — {e}")

                self._log(step, f"{portal} done — ok={ok} skipped={skip}")
                total_ok   += ok
                total_skip += skip

            self._set_state(step, count=total_ok,
                            message=f"{total_ok} inserted, {total_skip} skipped")
            self._log(step, f"Insert complete — ok={total_ok} skipped={total_skip}")

        return self._launch(step, _insert)

    # ── STEP 3: Generate embeddings ───────────────────────────────────────────

    def run_embed(self, batch_size: int = 20) -> bool:
        """
        Generates OpenAI embeddings for all properties with NULL embedding.
        Uses PropertyManager to read pending rows and save vectors.
        """
        step = "embed"

        def _embed():


            manager = PropertyManager(self.database_url)
            client  = OpenAI(api_key=self.openai_api_key)

            rows  = manager.get_properties_without_embeddings()
            total = len(rows)
            self._log(step, f"Found {total} properties without embeddings")

            if total == 0:
                self._set_state(step, count=0, message="All embeddings up to date")
                return

            done = 0
            for i in range(0, total, batch_size):
                batch    = rows[i:i + batch_size]
                ids      = [r[0] for r in batch]
                texts    = [r[1] for r in batch]

                self._log(step, f"Batch {i // batch_size + 1} — {len(batch)} items")

                response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts,
                )

                for j, emb_obj in enumerate(response.data):
                    manager.save_embedding(ids[j], emb_obj.embedding)

                done += len(batch)
                self._set_state(step, count=done,
                                message=f"{done}/{total} embeddings generated")
                self._log(step, f"  batch done — {done}/{total}")
                time.sleep(0.5)  # Respect rate limits

            self._log(step, f"Embeddings complete — {done} generated")

        return self._launch(step, _embed)