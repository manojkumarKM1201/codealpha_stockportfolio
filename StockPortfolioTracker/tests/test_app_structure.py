"""
Tests for app.py compilation and UI structure.
"""

import ast
import py_compile
from pathlib import Path


def test_app_compilation():
    """Verify that app.py compiles cleanly to bytecode without syntax errors."""
    app_path = Path(__file__).parent.parent / "app.py"
    compiled = py_compile.compile(str(app_path), doraise=True)
    assert compiled is not None


def test_app_ast_structure():
    """Verify that app.py defines expected navigation pages and modules."""
    app_path = Path(__file__).parent.parent / "app.py"
    with open(app_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    assert tree is not None

    # Check key navigation pages exist in source code
    expected_pages = [
        "📊 Dashboard Overview",
        "💼 Holdings Management",
        "➕ Add Transaction",
        "📜 Transaction History",
        "📥 Reports & Settings",
    ]
    for page in expected_pages:
        assert page in source, f"Page '{page}' should be defined in app.py"

    # Check key visualization charts exist in source code
    assert "px.pie" in source or "go.Figure" in source
    assert "export_holdings_to_csv" in source
    assert "generate_portfolio_summary_txt" in source
