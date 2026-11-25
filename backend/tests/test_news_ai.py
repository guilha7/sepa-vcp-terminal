import base64
import io

import pytest
from PIL import Image

from app.services.ai_service import analyze_chart_screenshot, generate_trader_briefing
from app.services.news_sentiment import score_sentiment


def _sample_png_b64() -> str:
    img = Image.new("RGB", (320, 180), color=(15, 23, 42))
    # Draw green & red stripes simulating candles
    for x in range(40, 200):
        for y in range(60, 120):
            img.putpixel((x, y), (16, 185, 129))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_vader_financial_sentiment():
    pos = score_sentiment("NVIDIA beats earnings estimates and raises guidance on strong AI demand surge")
    neg = score_sentiment("Company misses revenue, faces SEC investigation and announces mass layoffs")
    neu = score_sentiment("Company schedules quarterly conference call for next Tuesday")

    assert pos["code"] == "positive"
    assert neg["code"] == "negative"
    assert neu["code"] == "neutral"


def test_ai_briefing_fallback_structure(monkeypatch):
    monkeypatch.setattr("app.services.ai_service.detect_active_ai_provider", lambda: "fallback")

    briefing = generate_trader_briefing(
        ticker="NVDA",
        sepa_data={
            "price": 140.0,
            "score": 84.0,
            "trend_template": {"passed": True, "passed_count": 8, "relative_strength": {"rs_rating": 92}},
            "vcp": {"detected": True, "breakout_signal": True, "pivot_price": 138.0, "breakout_volume_ratio": 1.8},
            "trade_plan": {"entry_pivot": 138.0, "stop_loss_price": 130.0, "stop_loss_pct": 5.8},
        },
        fundamentals={"revenue_growth": 0.65, "earnings_growth": 0.80, "earnings_within_14d": False},
        news_data={
            "sentiment_summary": {"overall": "Positivo", "average_score": 0.4},
            "items": [{"title": "NVDA surges on record demand", "sentiment": {"code": "positive", "label": "Positivo"}}],
        },
        force_refresh=True,
    )

    assert briefing["ai_mode"] == "fallback"
    assert len(briefing["catalysts"]) >= 1
    assert len(briefing["risks"]) >= 1
    assert "NVDA" in briefing["verdict"] or "ATRATIVO" in briefing["verdict"]


def test_vision_analyzer_accepts_png_and_enforces_stop_cap(monkeypatch):
    monkeypatch.setattr("app.services.ai_service.detect_active_ai_provider", lambda: "fallback")
    b64 = _sample_png_b64()
    res = analyze_chart_screenshot(image_b64=b64, mime_type="image/png", ticker="NVDA")

    assert res["image_info"]["valid"] is True
    assert res["image_info"]["width"] == 320
    rep = res["report"]
    assert "trend_and_structure" in rep
    assert "patterns_and_levels" in rep
    assert "risk_assessment" in rep
    assert "trade_plan" in rep
    assert "study_tip" in rep
    assert rep["trade_plan"]["max_stop_pct"] <= 6.0


def test_vision_analyzer_rejects_invalid_image():
    with pytest.raises(ValueError):
        analyze_chart_screenshot(image_b64="not_valid_base64_image_data!!!")


def test_vision_stage4_downtrend_forces_evitar(monkeypatch):
    """When price is below SMA50 & SMA200 (like GALP.LS breakdown), fallback MUST output EVITAR."""
    monkeypatch.setattr("app.services.ai_service.detect_active_ai_provider", lambda: "fallback")
    b64 = _sample_png_b64()
    ticker_ctx = {
        "sepa": {
            "price": 18.195,
            "status": "FORA_STAGE_2",
            "score": 32.0,
            "trend_template": {
                "passed": False,
                "passed_count": 3,
                "metrics": {"sma50": 21.148, "sma200": 19.764},
            },
            "vcp": {
                "detected": False,
                "pivot_price": 23.04,
                "distance_to_pivot_pct": -21.03,
                "tight_low": 18.075,
                "is_extended": False,
                "contractions_pct": [12.9, 12.2, 7.3],
                "summary": "Sem VCP.",
            },
            "trade_plan": {"entry_pivot": 23.04, "stop_loss_price": 21.658, "stop_loss_pct": 6.0},
            "quant": {"weinstein": {"stage": 4, "label": "Stage 4 (Queda)"}},
        },
        "fundamentals": {"earnings_within_14d": False},
        "news": {"sentiment_summary": {"overall": "Positivo"}, "items": []},
    }

    res = analyze_chart_screenshot(
        image_b64=b64,
        mime_type="image/png",
        ticker="GALP.LS",
        ticker_context=ticker_ctx,
    )
    rep = res["report"]
    assert rep["trade_plan"]["bias"] == "EVITAR"
    assert "NÃO ENTRAR" in rep["trade_plan"]["entry_zone"].upper()
    assert "STAGE 4" in rep["trend_and_structure"].upper() or "BAIXA" in rep["trend_and_structure"].upper()
    assert "FACA A CAIR" in rep["risk_assessment"].upper() or "STAGE 4" in rep["risk_assessment"].upper()


def test_gemini_vision_filters_thought_parts_and_compresses_image(monkeypatch):
    from app.config import settings
    from app.services.ai_service import _call_gemini_detailed, _prepare_vision_image_b64

    # 1. Large image compression -> JPEG <= 1280px
    large_img = Image.new("RGB", (2400, 1400), color=(20, 30, 50))
    buf = io.BytesIO()
    large_img.save(buf, format="PNG")
    comp_b64, comp_mime = _prepare_vision_image_b64(buf.getvalue(), max_dim=1280)
    assert comp_mime == "image/jpeg"
    decoded = Image.open(io.BytesIO(base64.b64decode(comp_b64)))
    assert max(decoded.size) == 1280

    # 2. Gemini 2.5 thought parts ignored so valid JSON is returned cleanly
    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"thought": True, "text": "Internal reasoning with {bad json"},
                                {"text": '{"verdict": "OK", "catalysts": ["A"], "risks": ["B"]}'},
                            ]
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            return FakeResp()

    orig_key = settings.gemini_api_key
    try:
        settings.gemini_api_key = "AIzaFakeTestKey12345"
        monkeypatch.setattr("app.services.ai_service.httpx.Client", FakeClient)
        text, model_used, err = _call_gemini_detailed("Prompt teste")
        assert err is None
        assert model_used is not None
        assert text == '{"verdict": "OK", "catalysts": ["A"], "risks": ["B"]}'
    finally:
        settings.gemini_api_key = orig_key
