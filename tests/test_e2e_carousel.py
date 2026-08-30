import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import sqlite3
import pytest
from backend.carousel_jobs import create_job, get_job, init_carousel_jobs_table
from app import _run_carousel_graph_background

# Mock do payload de app.py
@pytest.fixture
def mock_payload():
    return {
        "copy": "Slide 1\n\nSlide 2\n\nSlide 3",
        "brand": {"name": "Test Brand", "handle": "@test", "verified": True},
        "slides": {"min": 5, "max": 10, "preferred": 7},
        "canvas": {"width": 1080, "height": 1350, "format": "PNG", "quality": 95},
        "visual_preferences": {
            "image_style": "minimalist",
            "slide_hints": ["", "", ""],
            "include_photos": True,
            "allow_copy_rewrite": False,
        },
        "output_dir": "./outputs/carrosseis_test",
    }

def test_e2e_carousel_flow(tmp_path, monkeypatch, mock_payload):
    # Setup de BD temporário
    db_path = str(tmp_path / "test.db")
    checkpoints_path = str(tmp_path / "checkpoints.sqlite")
    
    # Mock settings
    class MockSettings:
        def __init__(self):
            self.db_path = db_path
            self.carousel_checkpoints = f"sqlite:///{checkpoints_path}"
            self.carousel_output_dir = str(tmp_path / "outputs")
            self.google_api_key = "dummy"
            self.text_model = "dummy"
            self.image_model = "dummy"
            self.fonts_dir = "assets/fonts"
        
    monkeypatch.setattr("config.get_settings", lambda: MockSettings())
    
    # Init jobs table
    conn = sqlite3.connect(db_path)
    init_carousel_jobs_table(conn)
    
    # Mock do LangGraph para não chamar a API real e focar na persistência e orquestração
    # Em vez disso, vamos mockar build_carousel_graph
    from langgraph.graph.state import StateGraph
    
    def dummy_graph(state):
        return {"slides_rendered": [{"file_path": "dummy.png", "degraded": True}]}
    
    workflow = StateGraph(dict)
    workflow.add_node("dummy", dummy_graph)
    workflow.set_entry_point("dummy")
    workflow.set_finish_point("dummy")
    app_mock = workflow.compile()
    
    monkeypatch.setattr("backend.carousel_graph.build_carousel_graph", lambda x: app_mock)
    
    # Simula app.py
    thread_id = create_job(conn)
    
    # Executa o worker síncrono para o teste
    _run_carousel_graph_background(thread_id, mock_payload)
    
    # Verifica o estado final no BD
    job = get_job(conn, thread_id)
    assert job["status"] == "completed"
