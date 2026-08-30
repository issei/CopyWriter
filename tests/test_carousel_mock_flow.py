import os
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.carousel_graph import build_carousel_graph_with_mock_factory
from backend.carousel_state import CarouselState

# Mock Factory para injetar nos nós
class FakeLLM:
    def __init__(self, expected_quality):
        self.expected_quality = expected_quality

    def generate_structured(self, messages, schema=None):
        prompt = str(messages)
        print("FakeLLM prompt:", prompt[:100])
        if "plan" in prompt.lower() or "planejamento" in prompt.lower():
            return {"slides": [{"papel": "hook", "texto_slide": "Texto inicial da copy intacta", "prompt_visual_pomelli": "visual 1"}]}
        if "art" in prompt.lower() or "arte" in prompt.lower():
            return {"global_style": "clean", "slides": [{"slide_id": 1, "image_brief": {"required": True}}]}
        if "validador" in prompt.lower():
            score = 85 if self.expected_quality == "approved" else 30
            print("content_validator score:", score)
            return {"score": score, "critical_failures": []}
        return {"prompts": [{"slide_id": 1, "prompt": "test", "required": True}]}

class FakeVisionModel:
    def __init__(self, expected_quality):
        self.expected_quality = expected_quality

    def evaluate_image(self, file_path, rubric):
        score = 85 if self.expected_quality == "approved" else 30
        print("evaluate_image score:", score)
        return {"score": score, "issues": []}

class FakeImageModel:
    def generate(self, prompt, width, height, seed=None):
        return b"fake_image_bytes"

class FakeFactory:
    def __init__(self, expected_quality="approved"):
        self.expected_quality = expected_quality

    def text_model(self, *args, **kwargs):
        return FakeLLM(self.expected_quality)
    
    def vision_model(self, *args, **kwargs):
        return FakeVisionModel(self.expected_quality)
    
    def image_model(self, *args, **kwargs):
        return FakeImageModel()


def test_fluxo_mock_aprovado(tmp_path, monkeypatch):
    # Mock settings
    class MockSettings:
        carousel_output_dir = str(tmp_path / "outputs")
        fonts_dir = "assets/fonts"
        carousel_max_revisions = 2
    monkeypatch.setattr("config.get_settings", lambda: MockSettings)

    factory = FakeFactory(expected_quality="approved")
    graph = build_carousel_graph_with_mock_factory(factory)
    
    payload = {
        "copy": "Texto inicial da copy intacta",
        "brand": {"name": "Test Brand", "handle": "@test", "verified": True},
        "slides": {"min": 1, "max": 1, "preferred": 1},
        "canvas": {"width": 1080, "height": 1350, "format": "PNG", "quality": 95},
        "visual_preferences": {
            "image_style": "minimalist",
            "slide_hints": ["visual 1"],
            "include_photos": True,
            "allow_copy_rewrite": False,
        },
        "execution": {"session_id": "test_approved"}
    }
    
    final_state = graph.invoke(payload)
    
    # Assert conditions from Checklist
    assert final_state["quality_decision"] == "approved"
    assert "export_package" in final_state or final_state.get("manifest_path")
    # Copy crítica intacta:
    assert final_state["copy"] == "Texto inicial da copy intacta"
    # Slides individuais no manifest:
    assert len(final_state.get("composed_slides", [])) > 0

def test_fluxo_mock_human_review(tmp_path, monkeypatch):
    class MockSettings:
        carousel_output_dir = str(tmp_path / "outputs")
        fonts_dir = "assets/fonts"
        carousel_max_revisions = 2
    monkeypatch.setattr("config.get_settings", lambda: MockSettings)

    factory = FakeFactory(expected_quality="human_review")
    graph = build_carousel_graph_with_mock_factory(factory)
    
    payload = {
        "copy": "Texto inicial para review",
        "brand": {"name": "Test Brand"},
        "slides": {"min": 1, "max": 1, "preferred": 1},
        "canvas": {"width": 1080, "height": 1350, "format": "PNG"},
        "visual_preferences": {},
        "execution": {}
    }
    
    final_state = graph.invoke(payload)
    
    assert final_state["quality_decision"] == "human_review"
