"""
LLM Layer — news sentiment analysis with multi-provider routing.
Publishes weight vectors to Redis Streams for strategy layer consumption.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

import aiohttp
import feedparser
import redis.asyncio as aioredis
import structlog
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()
log = structlog.get_logger()


# ════════════════════════════════════════════════════════
# Provider abstractions
# ════════════════════════════════════════════════════════

class ProviderKind(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


@dataclass(frozen=True)
class LLMRequest:
    system:      str
    user:        str
    temperature: float = 0.1
    max_tokens:  int   = 1024
    json_mode:   bool  = True
    request_tag: str   = "sentiment"


@dataclass
class LLMResponse:
    content:       str
    model:         str
    provider:      str
    input_tokens:  int   = 0
    output_tokens: int   = 0
    latency_ms:    int   = 0
    cached:        bool  = False


@dataclass
class ProviderConfig:
    kind:           ProviderKind
    priority:       int   = 0
    max_rpm:        int   = 60
    max_budget_usd: float = 50.0
    timeout_s:      float = 30.0
    enabled:        bool  = True


class BaseProvider(ABC):
    def __init__(self, config: ProviderConfig) -> None:
        self.config       = config
        self._spend_usd   = 0.0
        self._error_count = 0
        self._last_err    = 0.0

    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @abstractmethod
    async def complete(self, req: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    def estimate_cost(self, req: LLMRequest) -> float: ...

    def is_healthy(self) -> bool:
        if self._error_count >= 3 and time.time() - self._last_err < 60:
            return False
        if self._error_count >= 3:
            self._error_count = 0
        return self.config.enabled and self._spend_usd < self.config.max_budget_usd

    def record_error(self) -> None:
        self._error_count += 1; self._last_err = time.time()

    def record_success(self, cost: float) -> None:
        self._error_count = 0; self._spend_usd += cost


class OllamaProvider(BaseProvider):
    def __init__(self, config: ProviderConfig,
                 model: str = "mistral:7b-instruct-q4_K_M",
                 base_url: str = "http://localhost:11434") -> None:
        super().__init__(config)
        self._model    = model
        self._base_url = base_url

    @property
    def provider_id(self) -> str: return f"ollama/{self._model}"

    def estimate_cost(self, req: LLMRequest) -> float: return 0.0

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    async def complete(self, req: LLMRequest) -> LLMResponse:
        t0 = time.monotonic()
        payload = {"model": self._model, "stream": False,
                   "options": {"temperature": req.temperature, "num_predict": req.max_tokens},
                   "messages": [{"role": "system", "content": req.system},
                                 {"role": "user",   "content": req.user}]}
        if req.json_mode:
            payload["format"] = "json"
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self._base_url}/api/chat", json=payload,
                                   timeout=aiohttp.ClientTimeout(self.config.timeout_s)) as r:
                    r.raise_for_status()
                    data = await r.json()
        except Exception:
            self.record_error(); raise
        latency = int((time.monotonic() - t0) * 1000)
        self.record_success(0.0)
        return LLMResponse(content=data.get("message", {}).get("content", ""),
                           model=self._model, provider=self.provider_id,
                           input_tokens=data.get("prompt_eval_count", 0),
                           output_tokens=data.get("eval_count", 0),
                           latency_ms=latency)


class OpenAIProvider(BaseProvider):
    _IN  = 0.005 / 1000
    _OUT = 0.015 / 1000

    def __init__(self, api_key: str, config: ProviderConfig,
                 model: str = "gpt-4o") -> None:
        super().__init__(config)
        self._api_key = api_key
        self._model   = model

    @property
    def provider_id(self) -> str: return f"openai/{self._model}"

    def estimate_cost(self, req: LLMRequest) -> float:
        return 200 * self._IN + 300 * self._OUT

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def complete(self, req: LLMRequest) -> LLMResponse:
        t0      = time.monotonic()
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        body    = {"model": self._model, "temperature": req.temperature,
                   "max_tokens": req.max_tokens,
                   "messages": [{"role": "system", "content": req.system},
                                 {"role": "user",   "content": req.user}]}
        if req.json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post("https://api.openai.com/v1/chat/completions",
                                   headers=headers, json=body,
                                   timeout=aiohttp.ClientTimeout(self.config.timeout_s)) as r:
                    r.raise_for_status()
                    data = await r.json()
        except Exception:
            self.record_error(); raise
        latency = int((time.monotonic() - t0) * 1000)
        usage   = data.get("usage", {})
        cost    = usage.get("prompt_tokens", 0) * self._IN + usage.get("completion_tokens", 0) * self._OUT
        self.record_success(cost)
        return LLMResponse(content=data["choices"][0]["message"]["content"],
                           model=self._model, provider=self.provider_id,
                           input_tokens=usage.get("prompt_tokens", 0),
                           output_tokens=usage.get("completion_tokens", 0),
                           latency_ms=latency)


class AnthropicProvider(BaseProvider):
    _IN  = 0.003 / 1000
    _OUT = 0.015 / 1000

    def __init__(self, api_key: str, config: ProviderConfig,
                 model: str = "claude-sonnet-4-6") -> None:
        super().__init__(config)
        self._api_key = api_key
        self._model   = model

    @property
    def provider_id(self) -> str: return f"anthropic/{self._model}"

    def estimate_cost(self, req: LLMRequest) -> float:
        return 200 * self._IN + 300 * self._OUT

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def complete(self, req: LLMRequest) -> LLMResponse:
        t0      = time.monotonic()
        system  = req.system + ("\n\nOutput ONLY valid JSON." if req.json_mode else "")
        headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
        body    = {"model": self._model, "max_tokens": req.max_tokens,
                   "temperature": req.temperature, "system": system,
                   "messages": [{"role": "user", "content": req.user},
                                 {"role": "assistant", "content": "{"}]}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post("https://api.anthropic.com/v1/messages",
                                   headers=headers, json=body,
                                   timeout=aiohttp.ClientTimeout(self.config.timeout_s)) as r:
                    r.raise_for_status()
                    data = await r.json()
        except Exception:
            self.record_error(); raise
        latency = int((time.monotonic() - t0) * 1000)
        usage   = data.get("usage", {})
        cost    = usage.get("input_tokens", 0) * self._IN + usage.get("output_tokens", 0) * self._OUT
        self.record_success(cost)
        raw = "{" + (data.get("content", [{}])[0].get("text", ""))
        return LLMResponse(content=raw, model=self._model, provider=self.provider_id,
                           input_tokens=usage.get("input_tokens", 0),
                           output_tokens=usage.get("output_tokens", 0),
                           latency_ms=latency)


# ════════════════════════════════════════════════════════
# Router with caching
# ════════════════════════════════════════════════════════

class ProviderRouter:
    def __init__(self, providers: list[BaseProvider],
                 breaking_provider_id: str = "",
                 cache_ttl: int = 180) -> None:
        self._providers = sorted(providers, key=lambda p: p.config.priority)
        self._breaking  = breaking_provider_id
        self._cache: dict[str, tuple[LLMResponse, float]] = {}
        self._ttl   = cache_ttl

    def _cache_key(self, req: LLMRequest) -> str:
        return hashlib.sha256(f"{req.system}|{req.user}".encode()).hexdigest()[:16]

    def _get_cache(self, req: LLMRequest) -> LLMResponse | None:
        k = self._cache_key(req)
        if k in self._cache:
            r, ts = self._cache[k]
            if time.time() - ts < self._ttl:
                return LLMResponse(**{**r.__dict__, "cached": True})
        return None

    async def route(self, req: LLMRequest) -> LLMResponse:
        if cached := self._get_cache(req):
            return cached
        candidates = self._build_list(req)
        if not candidates:
            raise RuntimeError("No healthy providers available")
        last_exc = None
        for p in candidates:
            try:
                resp = await p.complete(req)
                self._cache[self._cache_key(req)] = (resp, time.time())
                log.info("llm_ok", provider=resp.provider, ms=resp.latency_ms, tag=req.request_tag)
                return resp
            except Exception as e:
                last_exc = e
                log.warning("provider_failed", provider=p.provider_id, err=str(e))
        raise RuntimeError(f"All providers failed: {last_exc}") from last_exc

    def _build_list(self, req: LLMRequest) -> list[BaseProvider]:
        healthy = [p for p in self._providers if p.is_healthy()]
        if req.request_tag == "breaking_news" and self._breaking:
            primary   = [p for p in healthy if p.provider_id == self._breaking]
            secondary = [p for p in healthy if p.provider_id != self._breaking]
            return primary + secondary
        return healthy


# ════════════════════════════════════════════════════════
# News aggregator
# ════════════════════════════════════════════════════════

SYMBOL_KEYWORDS = {
    "BTC-USDT": ["bitcoin", "btc", "crypto", "fed", "inflation", "etf"],
    "ETH-USDT": ["ethereum", "eth", "defi", "gas", "staking"],
}

RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://cryptopanic.com/news/rss/",
]

HIGH_IMPACT = ["fed", "fomc", "rate", "sec", "ban", "hack", "etf", "bankruptcy",
               "fraud", "acquisition", "partnership", "liquidation"]


@dataclass
class NewsItem:
    title:        str
    summary:      str
    source:       str
    published_ts: float
    symbols:      list[str] = field(default_factory=list)
    importance:   float     = 0.5

    @property
    def age_min(self) -> float:
        return (time.time() - self.published_ts) / 60

    @property
    def hash(self) -> str:
        return hashlib.md5(self.title.encode()).hexdigest()[:8]


class NewsAggregator:
    def __init__(self, newsapi_key: str | None = None,
                 max_age_h: float = 4.0, max_items: int = 15) -> None:
        self._newsapi_key = newsapi_key
        self._max_age_h   = max_age_h
        self._max_items   = max_items
        self._seen: set[str] = set()

    async def fetch(self, symbols: list[str]) -> list[NewsItem]:
        tasks = [self._rss(url) for url in RSS_FEEDS]
        if self._newsapi_key:
            tasks.append(self._newsapi(symbols))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        items: list[NewsItem] = []
        for r in results:
            if isinstance(r, list):
                items.extend(r)
        items = self._dedupe(items)
        items = [i for i in items if i.age_min < self._max_age_h * 60]
        items = self._tag_symbols(items, symbols)
        items = [i for i in items if i.symbols]
        items = self._score(items)
        items.sort(key=lambda x: x.importance / (x.age_min + 1), reverse=True)
        log.info("news_fetched", count=len(items))
        return items[:self._max_items]

    async def _rss(self, url: str) -> list[NewsItem]:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(8)) as r:
                    text = await r.text()
            feed  = feedparser.parse(text)
            items = []
            for e in feed.entries[:15]:
                pub = e.get("published_parsed")
                ts  = time.mktime(pub) if pub else time.time()
                summary = re.sub(r"<[^>]+>", "", e.get("summary", e.get("description", "")))[:400]
                items.append(NewsItem(title=e.get("title", "")[:150],
                                      summary=summary, source=feed.feed.get("title", url),
                                      published_ts=ts))
            return items
        except Exception as e:
            log.warning("rss_error", url=url, err=str(e))
            return []

    async def _newsapi(self, symbols: list[str]) -> list[NewsItem]:
        kws = set()
        for sym in symbols:
            kws.update(SYMBOL_KEYWORDS.get(sym, [])[:3])
        q = " OR ".join(list(kws)[:4])
        url = (f"https://newsapi.org/v2/everything?q={q}&sortBy=publishedAt"
               f"&pageSize=15&language=en&apiKey={self._newsapi_key}")
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(8)) as r:
                    data = await r.json()
            from datetime import datetime, timezone
            items = []
            for a in data.get("articles", []):
                ts = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00")).timestamp()
                items.append(NewsItem(title=a.get("title", "")[:150],
                                      summary=(a.get("description") or "")[:400],
                                      source=a.get("source", {}).get("name", "newsapi"),
                                      published_ts=ts, importance=0.7))
            return items
        except Exception as e:
            log.warning("newsapi_error", err=str(e))
            return []

    def _dedupe(self, items: list[NewsItem]) -> list[NewsItem]:
        out = []
        for i in items:
            if i.hash not in self._seen:
                self._seen.add(i.hash)
                out.append(i)
        if len(self._seen) > 3000:
            self._seen = set(list(self._seen)[-2000:])
        return out

    def _tag_symbols(self, items: list[NewsItem], symbols: list[str]) -> list[NewsItem]:
        for item in items:
            text = (item.title + " " + item.summary).lower()
            item.symbols = [s for s in symbols
                            if any(kw in text for kw in SYMBOL_KEYWORDS.get(s, []))]
        return items

    def _score(self, items: list[NewsItem]) -> list[NewsItem]:
        source_w = {"bloomberg": 1.0, "reuters": 0.95, "coindesk": 0.85, "cointelegraph": 0.75}
        for item in items:
            text  = (item.title + " " + item.summary).lower()
            src_w = next((w for k, w in source_w.items() if k in item.source.lower()), 0.6)
            hits  = sum(1 for kw in HIGH_IMPACT if kw in text)
            item.importance = min(src_w + hits * 0.08, 1.0)
        return items


# ════════════════════════════════════════════════════════
# Pydantic output schema
# ════════════════════════════════════════════════════════

class SymbolSentiment(BaseModel):
    symbol:      str
    score:       float = Field(ge=-1.0, le=1.0)
    confidence:  float = Field(ge=0.0,  le=1.0)
    horizon:     str   = "short"
    key_drivers: list[str] = []
    risk_events: list[str] = []

    @field_validator("score", "confidence", mode="before")
    @classmethod
    def rnd(cls, v): return round(float(v), 4)


class SentimentResult(BaseModel):
    sentiments:    list[SymbolSentiment]
    market_regime: str = "neutral"
    macro_summary: str = ""
    model_used:    str = ""
    analysis_ts:   int = Field(default_factory=time.time_ns)


SYSTEM_PROMPT = """\
You are a quantitative market analyst specialising in crypto markets.
Analyse news and return sentiment as JSON ONLY — no markdown, no explanations outside JSON.

Scoring: -1.0 = strongly bearish, 0 = neutral, +1.0 = strongly bullish.
Be conservative: prefer scores in [-0.6, 0.6] unless news is clearly extreme.

Output format:
{
  "sentiments": [
    {"symbol": "BTC-USDT", "score": 0.3, "confidence": 0.7,
     "horizon": "short", "key_drivers": ["..."], "risk_events": ["..."]}
  ],
  "market_regime": "risk_on",
  "macro_summary": "one sentence"
}"""


def _build_prompt(symbols: list[str], news: list[NewsItem]) -> str:
    block = ""
    for i, n in enumerate(news[:12], 1):
        block += (f"{i}. [{n.source} | {n.age_min:.0f}min ago | imp={n.importance:.1f}]\n"
                  f"   {n.title}\n   {n.summary[:250]}\n\n")
    return f"Analyse sentiment for: {', '.join(symbols)}\n\nNews:\n{block}"


def _extract_json(raw: str) -> str:
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
    s, e = raw.find("{"), raw.rfind("}")
    return raw[s:e+1] if s != -1 and e != -1 else raw


async def analyse(router: ProviderRouter, symbols: list[str],
                  news: list[NewsItem], importance: float = 0.5) -> SentimentResult:
    if not news:
        return SentimentResult(sentiments=[SymbolSentiment(symbol=s, score=0, confidence=0)
                                           for s in symbols])
    tag = "breaking_news" if importance >= 0.8 else "sentiment"
    req = LLMRequest(system=SYSTEM_PROMPT, user=_build_prompt(symbols, news),
                     temperature=0.1, max_tokens=1024, json_mode=True, request_tag=tag)
    resp = await router.route(req)
    try:
        data = json.loads(_extract_json(resp.content))
    except Exception:
        log.warning("json_parse_fail", raw=resp.content[:200])
        return SentimentResult(sentiments=[SymbolSentiment(symbol=s, score=0, confidence=0)
                                           for s in symbols], model_used=resp.model)
    existing = {s["symbol"] for s in data.get("sentiments", [])}
    for sym in symbols:
        if sym not in existing:
            data.setdefault("sentiments", []).append(
                {"symbol": sym, "score": 0.0, "confidence": 0.0})
    data["model_used"]  = resp.model
    data["analysis_ts"] = time.time_ns()
    try:
        return SentimentResult.model_validate(data)
    except Exception:
        return SentimentResult(sentiments=[SymbolSentiment(symbol=s, score=0, confidence=0)
                                           for s in symbols], model_used=resp.model)


# ════════════════════════════════════════════════════════
# Weight computation & Redis publishing
# ════════════════════════════════════════════════════════

@dataclass
class WeightVector:
    symbol:      str
    llm_score:   float
    confidence:  float
    horizon:     str
    key_drivers: list[str]
    risk_events: list[str]
    model_used:  str
    ts_ns:       int   = field(default_factory=time.time_ns)


class WeightComputor:
    def __init__(self, half_life_min: float = 30.0) -> None:
        self._hl_s = half_life_min * 60
        self._hist: dict[str, list[WeightVector]] = {}

    def compute(self, result: SentimentResult) -> list[WeightVector]:
        vectors = []
        for sent in result.sentiments:
            score = self._regime_adjust(sent.score, result.market_regime)
            vec   = WeightVector(symbol=sent.symbol, llm_score=score,
                                 confidence=sent.confidence, horizon=sent.horizon,
                                 key_drivers=sent.key_drivers, risk_events=sent.risk_events,
                                 model_used=result.model_used)
            vec = self._decay_merge(vec)
            hist = self._hist.setdefault(sent.symbol, [])
            hist.append(vec)
            self._hist[sent.symbol] = hist[-10:]
            vectors.append(vec)
        return vectors

    def _regime_adjust(self, score: float, regime: str) -> float:
        if regime == "risk_on":
            score = score * 1.1 if score > 0 else score * 0.9
        elif regime == "risk_off":
            score = score * 0.9 if score > 0 else score * 1.1
        return max(-1.0, min(1.0, round(score, 4)))

    def _decay_merge(self, new: WeightVector) -> WeightVector:
        hist = self._hist.get(new.symbol, [])
        if not hist:
            return new
        now  = time.time()
        ws   = new.llm_score * new.confidence
        wt   = new.confidence
        for old in hist:
            age   = now - old.ts_ns / 1e9
            decay = math.exp(-age * math.log(2) / self._hl_s)
            w     = old.confidence * decay
            ws   += old.llm_score * w
            wt   += w
        merged = max(-1.0, min(1.0, round(ws / wt, 4))) if wt else new.llm_score
        return WeightVector(symbol=new.symbol, llm_score=merged,
                            confidence=new.confidence, horizon=new.horizon,
                            key_drivers=new.key_drivers, risk_events=new.risk_events,
                            model_used=new.model_used)


class WeightPublisher:
    TOPIC = "llm.weight"

    def __init__(self, redis_url: str) -> None:
        self._r = aioredis.from_url(redis_url, decode_responses=True)

    async def publish(self, vectors: list[WeightVector]) -> None:
        pipe = self._r.pipeline()
        for v in vectors:
            data = json.dumps({
                "symbol": v.symbol, "llm_score": v.llm_score,
                "confidence": v.confidence, "horizon": v.horizon,
                "key_drivers": v.key_drivers, "risk_events": v.risk_events,
                "model_used": v.model_used, "ts_ns": v.ts_ns, "ttl_ms": 300_000,
            })
            pipe.xadd(self.TOPIC, {"symbol": v.symbol, "score": str(v.llm_score),
                                    "conf": str(v.confidence), "data": data},
                      maxlen=1000, approximate=True)
            log.info("weight_published", symbol=v.symbol, score=v.llm_score,
                     model=v.model_used, drivers=v.key_drivers[:2])
        await pipe.execute()


# ════════════════════════════════════════════════════════
# Scheduler
# ════════════════════════════════════════════════════════

async def run_cycle(aggregator: NewsAggregator, router: ProviderRouter,
                    computor: WeightComputor, publisher: WeightPublisher,
                    symbols: list[str], importance_override: float | None = None) -> None:
    news       = await aggregator.fetch(symbols)
    importance = importance_override or (max((n.importance for n in news), default=0.5)
                                         if news else 0.5)
    result     = await analyse(router, symbols, news, importance)
    vectors    = computor.compute(result)
    await publisher.publish(vectors)
    log.info("cycle_done", regime=result.market_regime,
             scores={v.symbol: v.llm_score for v in vectors})


async def main() -> None:
    structlog.configure(processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ])
    log.info("llm_layer_starting")

    SYMBOLS  = ["BTC-USDT", "ETH-USDT"]
    REDIS    = os.getenv("REDIS_URL", "redis://localhost:6379")
    INTERVAL = float(os.getenv("LLM_INTERVAL_S", "300"))
    BREAK_TH = float(os.getenv("BREAKING_THRESHOLD", "0.85"))

    ollama = OllamaProvider(
        ProviderConfig(kind=ProviderKind.LOCAL, priority=0, timeout_s=45),
        model    = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct-q4_K_M"),
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )
    providers: list[BaseProvider] = [ollama]

    if key := os.getenv("ANTHROPIC_API_KEY"):
        providers.append(AnthropicProvider(key,
            ProviderConfig(kind=ProviderKind.CLOUD, priority=1, max_budget_usd=30)))

    if key := os.getenv("OPENAI_API_KEY"):
        providers.append(OpenAIProvider(key,
            ProviderConfig(kind=ProviderKind.CLOUD, priority=2, max_budget_usd=20)))

    breaking_id = providers[1].provider_id if len(providers) > 1 else ""
    router      = ProviderRouter(providers, breaking_provider_id=breaking_id, cache_ttl=180)
    aggregator  = NewsAggregator(newsapi_key=os.getenv("NEWSAPI_KEY"), max_age_h=4, max_items=15)
    computor    = WeightComputor(half_life_min=30)
    publisher   = WeightPublisher(REDIS)

    last_breaking = 0.0

    async def routine_loop():
        while True:
            try:
                await run_cycle(aggregator, router, computor, publisher, SYMBOLS)
            except Exception:
                log.exception("routine_error")
            await asyncio.sleep(INTERVAL)

    async def breaking_monitor():
        nonlocal last_breaking
        while True:
            try:
                news = await aggregator.fetch(SYMBOLS)
                if news:
                    max_imp = max(n.importance for n in news)
                    if max_imp >= BREAK_TH and time.time() - last_breaking > 60:
                        log.info("breaking_news", importance=max_imp, title=news[0].title[:80])
                        await run_cycle(aggregator, router, computor, publisher,
                                        SYMBOLS, importance_override=max_imp)
                        last_breaking = time.time()
            except Exception:
                log.exception("breaking_error")
            await asyncio.sleep(30)

    await asyncio.gather(routine_loop(), breaking_monitor())


if __name__ == "__main__":
    asyncio.run(main())
