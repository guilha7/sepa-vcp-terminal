import base64
import io
import json
import logging
import re
from typing import Any, Optional

import httpx
from PIL import Image

from app.config import settings
from app.database import db

logger = logging.getLogger(__name__)


def detect_active_ai_provider() -> str:
    """Determines which AI provider is active according to .env configuration."""
    pref = (settings.ai_provider or "auto").strip().lower()
    if pref == "none":
        return "fallback"
    if pref == "gemini":
        return "gemini" if settings.gemini_api_key.strip() else "fallback"
    if pref == "ollama":
        return "ollama" if _is_ollama_reachable() else "fallback"

    # auto: Gemini first (if key set), then local Ollama, else deterministic fallback
    if settings.gemini_api_key.strip():
        return "gemini"
    if _is_ollama_reachable():
        return "ollama"
    return "fallback"


def _is_ollama_reachable() -> bool:
    try:
        url = settings.ollama_base_url.rstrip("/") + "/api/tags"
        with httpx.Client(timeout=0.45) as client:
            resp = client.get(url)
            return resp.status_code == 200
    except Exception:
        return False


def _extract_json_block(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    cleaned = text.strip()
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except Exception:
        pass
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None


def _call_gemini(prompt: str, image_b64: Optional[str] = None, mime_type: str = "image/png") -> Optional[str]:
    api_key = settings.gemini_api_key.strip()
    if not api_key:
        return None
    preferred = settings.gemini_model.strip() or "gemini-2.5-flash"
    # Try preferred model first, then automatic free-tier fallbacks on 404
    candidates_models = list(
        dict.fromkeys([preferred, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest", "gemini-1.5-flash"])
    )

    parts: list[dict[str, Any]] = [{"text": prompt}]
    if image_b64:
        parts.append({"inline_data": {"mime_type": mime_type, "data": image_b64}})

    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.25,
            "responseMimeType": "application/json",
        },
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    with httpx.Client(timeout=35.0) as client:
        for model in candidates_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                resp = client.post(url, json=body, headers=headers)
                if resp.status_code == 404:
                    logger.debug("Modelo Gemini %s devolveu 404; a tentar fallback...", model)
                    continue
                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates") or []
                if not candidates:
                    continue
                out_parts = candidates[0].get("content", {}).get("parts") or []
                text = "".join(p.get("text", "") for p in out_parts).strip()
                if text:
                    return text
            except Exception as exc:
                logger.warning("Chamada Gemini API (%s) falhou: %s", model, type(exc).__name__)
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (401, 403):
                    break
    return None


def _call_ollama(prompt: str, image_b64: Optional[str] = None) -> Optional[str]:
    base = settings.ollama_base_url.rstrip("/")
    model = settings.ollama_vision_model if image_b64 else settings.ollama_model
    url = f"{base}/api/chat"
    message: dict[str, Any] = {"role": "user", "content": prompt}
    if image_b64:
        message["images"] = [image_b64]

    body = {
        "model": model,
        "messages": [message],
        "stream": False,
        "format": "json",
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            return (data.get("message") or {}).get("content")
    except Exception as exc:
        logger.warning("Chamada Ollama local falhou (%s): %s", model, exc)
        return None


def _fallback_trader_briefing(
    ticker: str,
    sepa_data: dict[str, Any],
    fundamentals: dict[str, Any],
    news_data: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic zero-cost local briefing when Gemini/Ollama are not configured."""
    tt = sepa_data.get("trend_template", {})
    vcp = sepa_data.get("vcp", {})
    plan = sepa_data.get("trade_plan", {})
    sent = news_data.get("sentiment_summary", {})
    items = news_data.get("items") or []

    catalysts: list[str] = []
    if tt.get("passed"):
        catalysts.append(
            f"Estrutura técnica Stage 2 confirmada (8/8 regras de Minervini) com RS Rating ~{tt.get('relative_strength', {}).get('rs_rating', 50)}/99."
        )
    if vcp.get("breakout_signal"):
        catalysts.append(
            f"Breakout detetado acima de {vcp.get('pivot_price')} com volume {vcp.get('breakout_volume_ratio')}x a média de 50 dias."
        )
    elif vcp.get("detected"):
        c_str = " → ".join(f"{x:.1f}%" for x in (vcp.get("contractions_pct") or []))
        catalysts.append(f"Contração de volatilidade (VCP: {c_str}) perto do pivô {vcp.get('pivot_price')}.")

    rev_g = fundamentals.get("revenue_growth")
    earn_g = fundamentals.get("earnings_growth")
    if rev_g is not None and rev_g > 0.15:
        catalysts.append(f"Crescimento forte de receitas (+{rev_g * 100:.1f}% YoY).")
    if earn_g is not None and earn_g > 0.15:
        catalysts.append(f"Aceleração de lucros (+{earn_g * 100:.1f}% YoY).")

    pos_headlines = [n["title"] for n in items if n["sentiment"]["code"] == "positive"][:2]
    for h in pos_headlines:
        catalysts.append(f"Notícia positiva: {h}")

    if not catalysts:
        catalysts.append("Sem catalisadores fortes identificados nas notícias recentes ou na estrutura VCP.")

    risks: list[str] = []
    if fundamentals.get("earnings_within_14d"):
        risks.append(
            f"EARNINGS IMINENTES em {fundamentals.get('next_earnings_date')} ({fundamentals.get('days_to_earnings')} dias) — risco elevado de gap acima do stop de 6%."
        )
    if not tt.get("passed"):
        risks.append(f"Ainda fora do Stage 2 perfeito ({tt.get('passed_count', 0)}/8 regras cumpridas).")
    if vcp.get("is_extended"):
        risks.append("Preço esticado face ao pivô/SMA 50 — perseguir entradas aumenta risco de stop-out.")
    if sent.get("overall") == "Negativo":
        risks.append(f"Fluxo de notícias recente com viés negativo (score VADER {sent.get('average_score', 0):+.2f}).")

    neg_headlines = [n["title"] for n in items if n["sentiment"]["code"] == "negative"][:2]
    for h in neg_headlines:
        risks.append(f"Notícia de risco: {h}")
    if not risks:
        risks.append("Risco de mercado geral e possível falso breakout (fakeout) se o volume não confirmar.")

    score = sepa_data.get("score", 0)
    if score >= 75 and tt.get("passed") and not fundamentals.get("earnings_within_14d"):
        verdict = (
            f"ATRATIVO (Score {score}/100): Alinhamento técnico SEPA sólido. Monitorizar pivô em {plan.get('entry_pivot')} "
            f"com stop rigoroso em {plan.get('stop_loss_price')} (-{plan.get('stop_loss_pct')}%)."
        )
    elif score >= 55:
        verdict = (
            f"EM OBSERVAÇÃO (Score {score}/100): Potencial em desenvolvimento, mas aguarda melhor aperto VCP, "
            f"confirmação de volume ou clarificação de catalisadores antes de arriscar capital."
        )
    else:
        verdict = (
            f"EVITAR / AGUARDAR (Score {score}/100): Não cumpre os critérios de liderança Stage 2 de Minervini. "
            f"Preserva capital para ativos com maior Força Relativa."
        )

    return {
        "provider": "Análise Algorítmica Local (Sem IA Externa)",
        "ai_mode": "fallback",
        "catalysts": catalysts[:4],
        "risks": risks[:4],
        "verdict": verdict,
        "note": "Para briefings gerados por LLM, configura GEMINI_API_KEY (grátis) ou inicia o Ollama localmente no ficheiro .env.",
    }


def generate_trader_briefing(
    ticker: str,
    sepa_data: dict[str, Any],
    fundamentals: dict[str, Any],
    news_data: dict[str, Any],
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Generates a concise structured Trader Briefing using Gemini, Ollama, or local fallback."""
    cache_key = f"ai:briefing:{ticker}"
    if not force_refresh:
        cached = db.cache_get(cache_key)
        if cached and isinstance(cached, dict):
            return cached

    provider = detect_active_ai_provider()
    if provider == "fallback":
        return _fallback_trader_briefing(ticker, sepa_data, fundamentals, news_data)

    headlines = [
        f"- [{it['sentiment']['label']}] {it['title']} ({it['source']})"
        for it in (news_data.get("items") or [])[:8]
    ]
    prompt = f"""
Atua como um Analista Quantitativo sénior especialista na metodologia SEPA/VCP de Mark Minervini.
Analisa o ativo {ticker} em Português de Portugal de forma concisa, objetiva e sem floreados.

DADOS TÉCNICOS:
- Preço: {sepa_data.get('price')} (variação dia: {sepa_data.get('daily_change_pct')}%)
- Score SEPA/VCP: {sepa_data.get('score')}/100 | Status: {sepa_data.get('status')}
- Regras Minervini: {sepa_data.get('trend_template', {}).get('passed_count')}/8
- RS Rating: {sepa_data.get('trend_template', {}).get('relative_strength', {}).get('rs_rating')}/99
- VCP: {sepa_data.get('vcp', {}).get('summary')}
- Plano sugerido: Pivô {sepa_data.get('trade_plan', {}).get('entry_pivot')}, Stop {sepa_data.get('trade_plan', {}).get('stop_loss_price')} (-{sepa_data.get('trade_plan', {}).get('stop_loss_pct')}%)

FUNDAMENTAIS:
- Setor: {fundamentals.get('sector')} | P/E: {fundamentals.get('trailing_pe')}
- Crescimento Receitas: {fundamentals.get('revenue_growth')} | Lucros: {fundamentals.get('earnings_growth')}
- Próximos Earnings: {fundamentals.get('next_earnings_date')} (em 14d: {fundamentals.get('earnings_within_14d')})

NOTÍCIAS RECENTES (Sentimento global: {news_data.get('sentiment_summary', {}).get('overall')}):
{chr(10).join(headlines) if headlines else 'Sem notícias recentes.'}

Devolve APENAS JSON válido com esta estrutura exata:
{{
  "catalysts": ["lista de 2 a 4 catalisadores objetivos"],
  "risks": ["lista de 2 a 4 riscos concretos incluindo técnicos/earnings/notícias"],
  "verdict": "Veredito objetivo de 2-3 frases com postura clara (Ex: Comprar no Pivô / Aguardar / Evitar) respeitando stop <= 6%."
}}
""".strip()

    raw = _call_gemini(prompt) if provider == "gemini" else _call_ollama(prompt)
    parsed = _extract_json_block(raw or "")
    if parsed and parsed.get("verdict"):
        result = {
            "provider": f"Google Gemini ({settings.gemini_model})" if provider == "gemini" else f"Ollama Local ({settings.ollama_model})",
            "ai_mode": provider,
            "catalysts": parsed.get("catalysts") or [],
            "risks": parsed.get("risks") or [],
            "verdict": str(parsed.get("verdict")),
            "note": None,
        }
        db.cache_set(cache_key, "ai", result, settings.cache_ttl_ai)
        return result

    fallback = _fallback_trader_briefing(ticker, sepa_data, fundamentals, news_data)
    fallback["note"] = f"Fallback algorítmico usado porque o provedor {provider} não devolveu resposta válida."
    return fallback


def _inspect_image_metadata(image_bytes: bytes) -> dict[str, Any]:
    """Extracts basic visual metadata (dimensions, color ratio) for validation and local fallback."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        small = img.resize((96, 64))
        raw_rgb = small.tobytes()
        pixels = [(raw_rgb[i], raw_rgb[i + 1], raw_rgb[i + 2]) for i in range(0, len(raw_rgb), 3)]
        green_px = sum(1 for r, g, b in pixels if g > r + 20 and g > b + 15)
        red_px = sum(1 for r, g, b in pixels if r > g + 20 and r > b + 15)
        total = len(pixels) or 1
        return {
            "valid": True,
            "width": w,
            "height": h,
            "green_pct": round(green_px / total * 100.0, 2),
            "red_pct": round(red_px / total * 100.0, 2),
        }
    except Exception:
        return {"valid": False, "width": 0, "height": 0, "green_pct": 0.0, "red_pct": 0.0}


def analyze_chart_screenshot(
    image_b64: str,
    mime_type: str = "image/png",
    ticker: Optional[str] = None,
    timeframe: Optional[str] = None,
    user_notes: Optional[str] = None,
    ticker_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Module 4: Vision AI Chart Screenshot Analyzer.
    Supports Gemini Free Tier Vision, Ollama Local Vision (qwen2.5-vl / llama3.2-vision),
    and a clean structured fallback enriched with live ticker context when provided.
    """
    # Strip optional data URI prefix
    clean_b64 = image_b64.strip()
    if "," in clean_b64 and clean_b64.startswith("data:"):
        header, clean_b64 = clean_b64.split(",", 1)
        m = re.search(r"data:([^;]+);base64", header)
        if m:
            mime_type = m.group(1)

    try:
        raw_bytes = base64.b64decode(clean_b64)
    except Exception:
        raise ValueError("Imagem base64 inválida.")

    img_meta = _inspect_image_metadata(raw_bytes)
    if not img_meta["valid"]:
        raise ValueError("O ficheiro enviado não é uma imagem válida (PNG/JPG/WEBP).")

    provider = detect_active_ai_provider()

    context_block = ""
    if ticker_context:
        sepa = ticker_context.get("sepa", {})
        news = ticker_context.get("news", {})
        fund = ticker_context.get("fundamentals", {})
        top_news = "; ".join(it["title"] for it in (news.get("items") or [])[:4]) or "Sem manchetes recentes"
        context_block = f"""
CONTEXTO EM TEMPO REAL DO TICKER {ticker}:
- Preço atual: {sepa.get('price')} | Status SEPA: {sepa.get('status')} (Score {sepa.get('score')}/100)
- Trend Template: {sepa.get('trend_template', {}).get('passed_count')}/8 regras
- VCP Detetado: {sepa.get('vcp', {}).get('summary')}
- Plano Quantitativo: Pivô {sepa.get('trade_plan', {}).get('entry_pivot')}, Stop {sepa.get('trade_plan', {}).get('stop_loss_price')} (-{sepa.get('trade_plan', {}).get('stop_loss_pct')}%)
- Earnings em 14 dias: {fund.get('earnings_within_14d')} ({fund.get('next_earnings_date') or 'N/D'})
- Sentimento Notícias: {news.get('sentiment_summary', {}).get('overall')} | Manchetes: {top_news}
"""

    prompt = f"""
Atua como um Trader Institucional e Analista Técnico especialista na metodologia SEPA/VCP de Mark Minervini.
Analisa cuidadosamente o screenshot de gráfico anexado em Português de Portugal.
Ticker indicado: {ticker or 'Não especificado'} | Timeframe indicado: {timeframe or 'Detetar no gráfico'}
Notas do utilizador: {user_notes or 'Nenhuma'}
{context_block}

REGRA CRÍTICA DE RISCO: Qualquer sugestão de plano de trade deve respeitar rigorosamente um Stop-Loss máximo de <= 6% (nunca sugerir stop superior a 6%).

Devolve APENAS JSON válido com esta estrutura exata:
{{
  "trend_and_structure": "Análise clara da tendência principal (Stage 1/2/3/4), estrutura de máximos/mínimos e alinhamento face às médias móveis visíveis.",
  "patterns_and_levels": "Padrões detetados (VCP, Cup & Handle, Base Plana, Triângulo, Canal, etc.) e níveis-chave de Suporte, Resistência e Pivô visíveis.",
  "risk_assessment": "Avaliação objetiva de risco: possibilidade de fakeout/bull trap, extensão excessiva acima das médias, sinais de distribuição/volume e risco de earnings se aplicável.",
  "trade_plan": {{
    "bias": "COMPRA_NO_PIVO | AGUARDAR_CONSOLIDACAO | EVITAR",
    "entry_zone": "Zona ou condição clara de entrada",
    "stop_loss_rule": "Nível/regra de stop-loss <= 6%",
    "targets": "Alvos 2R e 3R sugeridos",
    "max_stop_pct": 6.0
  }},
  "study_tip": "Uma dica pedagógica prática sobre o que o trader deve treinar o olho a observar neste gráfico específico."
}}
""".strip()

    report: Optional[dict[str, Any]] = None
    used_provider_label = "Análise Local (Sem Modelo de Visão Ativo)"
    ai_mode = "fallback"
    warning_msg: Optional[str] = None

    if provider in ("gemini", "ollama"):
        raw = _call_gemini(prompt, image_b64=clean_b64, mime_type=mime_type) if provider == "gemini" else _call_ollama(prompt, image_b64=clean_b64)
        parsed = _extract_json_block(raw or "")
        if parsed and parsed.get("trend_and_structure"):
            report = parsed
            ai_mode = provider
            used_provider_label = (
                f"Google Gemini Vision ({settings.gemini_model})"
                if provider == "gemini"
                else f"Ollama Vision ({settings.ollama_vision_model})"
            )
        else:
            warning_msg = f"O motor de visão {provider} não respondeu com JSON válido; foi ativado o fallback estruturado."

    if report is None:
        # Clean, transparent fallback enriched with live quantitative ticker data when ticker is supplied
        if ticker_context and ticker_context.get("sepa"):
            sepa = ticker_context["sepa"]
            tt = sepa.get("trend_template", {})
            vcp = sepa.get("vcp", {})
            plan = sepa.get("trade_plan", {})
            fund = ticker_context.get("fundamentals", {})
            news = ticker_context.get("news", {})
            c_str = " → ".join(f"{x:.1f}%" for x in (vcp.get("contractions_pct") or []))
            report = {
                "trend_and_structure": (
                    f"[Análise Quantitativa de {ticker} — Visão IA offline] "
                    f"Trend Template {tt.get('passed_count', 0)}/8 regras ({'Stage 2 confirmado' if tt.get('passed') else 'Fora de Stage 2 completo'}). "
                    f"Preço atual {sepa.get('price')} face a SMA50 {tt.get('metrics', {}).get('sma50')} e SMA200 {tt.get('metrics', {}).get('sma200')}."
                ),
                "patterns_and_levels": (
                    f"Pivô/Resistência detetada em {vcp.get('pivot_price')} (distância {vcp.get('distance_to_pivot_pct')}%). "
                    f"Suporte curto (mínimo 10 sessões) em {vcp.get('tight_low')}. Amplitudes recentes: {c_str or 'N/D'}. {vcp.get('summary')}"
                ),
                "risk_assessment": (
                    f"{'ALERTA: Preço esticado — risco de pullback/fakeout. ' if vcp.get('is_extended') else 'Sem sobre-extensão crítica face à SMA50. '}"
                    f"{'ALERTA EARNINGS em ' + str(fund.get('next_earnings_date')) + ' (< 14 dias)! ' if fund.get('earnings_within_14d') else ''}"
                    f"Sentimento de notícias: {news.get('sentiment_summary', {}).get('overall', 'Neutro')}."
                ),
                "trade_plan": {
                    "bias": "COMPRA_NO_PIVO" if (tt.get("passed") and not vcp.get("is_extended")) else "AGUARDAR_CONSOLIDACAO",
                    "entry_zone": f"Pivô em {plan.get('entry_pivot')} com volume >= 1.5x média 50d",
                    "stop_loss_rule": f"Stop técnico em {plan.get('stop_loss_price')} (-{plan.get('stop_loss_pct')}%, respeitando limite <= 6%)",
                    "targets": f"2R em {plan.get('target_2r')} (+{plan.get('target_2r_pct')}%) | 3R em {plan.get('target_3r')} (+{plan.get('target_3r_pct')}%)",
                    "max_stop_pct": plan.get("stop_loss_pct", 6.0),
                },
                "study_tip": (
                    "Verifica visualmente no print se os candles perto da resistência estão a ficar mais estreitos "
                    "e se as barras de volume diminuíram antes da rutura (Volume Dry-Up). Configura GEMINI_API_KEY "
                    "(grátis) ou Ollama (qwen2.5-vl / llama3.2-vision) no .env para leitura visual direta dos candles."
                ),
            }
        else:
            color_hint = (
                "predominância visual de elementos verdes/alta"
                if img_meta["green_pct"] > img_meta["red_pct"] * 1.15
                else (
                    "predominância visual de elementos vermelhos/correção"
                    if img_meta["red_pct"] > img_meta["green_pct"] * 1.15
                    else "equilíbrio visual entre candles positivos e negativos"
                )
            )
            report = {
                "trend_and_structure": (
                    f"Imagem recebida ({img_meta['width']}x{img_meta['height']}px, {color_hint}), mas nenhum motor de Visão IA "
                    f"(Gemini API Free Tier ou Ollama local) está ativo neste momento."
                ),
                "patterns_and_levels": (
                    "Indica o ticker no campo acima para cruzar automaticamente com dados quantitativos SEPA/VCP e notícias, "
                    "ou ativa o Gemini Free Tier / Ollama Vision no ficheiro .env para análise visual completa de suportes e resistências."
                ),
                "risk_assessment": (
                    "Checklist manual anti-fakeout: 1) O preço está acima das SMAs 50/150/200? "
                    "2) A distância até à SMA 50 é inferior a 15%? 3) O volume contraiu na base e expandiu >= 1.5x no rompimento?"
                ),
                "trade_plan": {
                    "bias": "AGUARDAR_CONSOLIDACAO",
                    "entry_zone": "Apenas na rutura limpa do pivô de resistência após aperto de volatilidade",
                    "stop_loss_rule": "Stop-Loss rígido <= 6% abaixo do preço de entrada (ou abaixo do último mínimo apertado)",
                    "targets": "Realizar parcial em 2R (+12% se stop 6%) e proteger lucro rumo a 3R (+18%)",
                    "max_stop_pct": 6.0,
                },
                "study_tip": (
                    "Para ativar Visão IA 100% gratuita: obtém uma chave grátis em aistudio.google.com/apikey e coloca "
                    "GEMINI_API_KEY=... no ficheiro .env, OU corre 'ollama pull qwen2.5-vl' localmente."
                ),
            }

    # Enforce strict <= 6% stop cap in report output
    tp = report.get("trade_plan") or {}
    try:
        tp["max_stop_pct"] = min(float(tp.get("max_stop_pct", 6.0)), 6.0)
    except Exception:
        tp["max_stop_pct"] = 6.0
    report["trade_plan"] = tp

    result = {
        "ticker": ticker,
        "provider": used_provider_label,
        "ai_mode": ai_mode,
        "image_info": img_meta,
        "report": report,
        "ticker_context": ticker_context,
        "warning": warning_msg,
    }
    db.save_vision_report(ticker=ticker, provider=used_provider_label, report=report)
    return result
