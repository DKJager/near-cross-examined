import sys
import os
import json
import pathlib
import tempfile
import shutil
import re
from unittest import mock
import contextlib
import io

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [_R, os.path.join(_R, "src")]

def test_every_chart_has_sentence_and_method():
    """dashboard.py: test that every chart <figure> has a <figcaption>, a <p class="says"> and a <details> with metric path"""
    # Setup
    import dashboard
    
    # Create a temporary copy of required files
    tmpdir = tempfile.mkdtemp()
    try:
        # Copy necessary files
        out_dir = os.path.join(tmpdir, "out")
        os.makedirs(out_dir)
        
        # Load real files to copy
        root = pathlib.Path(_R)
        with open(root / "out" / "metrics.json", "r") as f:
            metrics = json.load(f)
        with open(root / "out" / "panel.json", "r") as f:
            panel = json.load(f)
        with open(root / "forecasts.json", "r") as f:
            forecasts = json.load(f)
        with open(root / "tripwires.json", "r") as f:
            tripwires = json.load(f)
        
        # Write copies
        with open(os.path.join(out_dir, "metrics.json"), "w") as f:
            json.dump(metrics, f)
        with open(os.path.join(out_dir, "panel.json"), "w") as f:
            json.dump(panel, f)
        with open(os.path.join(tmpdir, "forecasts.json"), "w") as f:
            json.dump(forecasts, f)
        with open(os.path.join(tmpdir, "tripwires.json"), "w") as f:
            json.dump(tripwires, f)
        
        # Change to tmpdir and build
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            # Capture output
            with contextlib.redirect_stdout(io.StringIO()):
                dashboard.build()
            
            # Read generated HTML
            html_path = os.path.join(out_dir, "index.html")
            with open(html_path, "r") as f:
                html = f.read()
            
            # Test assertions
            # Count figures
            figures = html.count("<figure>")
            assert figures == 11, f"dashboard.py: expected 11 <figure> elements, found {figures}"
            
            # Check each figure has required elements
            # Parse with regex for simplicity (HTML is from dashboard.py)
            # Find all figure content between <figure> and </figure>
            fig_pattern = r'<figure>(.*?)</figure>'
            figures_content = re.findall(fig_pattern, html, re.DOTALL)
            
            assert len(figures_content) == 11, f"dashboard.py: found {len(figures_content)} figure blocks, expected 11"
            
            for i, content in enumerate(figures_content, 1):
                # Must have figcaption
                assert "<figcaption>" in content, f"dashboard.py: figure {i} missing <figcaption>"
                
                # Must have p class="says"
                assert 'class="says"' in content, f"dashboard.py: figure {i} missing <p class=\"says\">"
                
                # Must have details element
                assert "<details>" in content, f"dashboard.py: figure {i} missing <details>"
                
                # Details must contain code element with metric path pattern
                # Extract details content
                details_pattern = r'<details>(.*?)</details>'
                details_match = re.search(details_pattern, content, re.DOTALL)
                assert details_match is not None, f"dashboard.py: figure {i} missing details content"
                details = details_match.group(1)
                
                # Find code elements
                code_pattern = r'<code>(.*?)</code>'
                code_matches = re.findall(code_pattern, details)
                assert len(code_matches) > 0, f"dashboard.py: figure {i} details missing <code> elements"
                
                # At least one code element should match metric path pattern
                metric_path_pattern = r'[a-z_0-9]+[.][A-Za-z_0-9.-]+'
                has_metric_path = any(re.match(metric_path_pattern, code) for code in code_matches)
                assert has_metric_path, f"dashboard.py: figure {i} code elements don't contain metric paths matching {metric_path_pattern}"
            
            # Check that two chain charts mention sql files
            chain_charts = ["Daily active accounts (monthly mean)", "Daily transactions (monthly mean)"]
            for chart_title in chain_charts:
                # Find figure with this caption
                figcap_pattern = rf'<figcaption>{re.escape(chart_title)}</figcaption>.*?<details>.*?</details>'
                match = re.search(figcap_pattern, html, re.DOTALL)
                assert match is not None, f"dashboard.py: chart '{chart_title}' not found or missing details"
                details = match.group(0)
                
                # Check for sql/ mention
                sql_pattern = r'sql/[a-z_]+\.sql'
                has_sql = re.search(sql_pattern, details) is not None
                assert has_sql, f"dashboard.py: chart '{chart_title}' details missing sql/ file reference"
                
        finally:
            os.chdir(old_cwd)
    finally:
        shutil.rmtree(tmpdir)

def test_hero_tiles_exact_values():
    """dashboard.py: test hero tiles appear before KPI tiles with exact computed values"""
    import dashboard
    
    # Create temporary copy
    tmpdir = tempfile.mkdtemp()
    try:
        out_dir = os.path.join(tmpdir, "out")
        os.makedirs(out_dir)
        
        root = pathlib.Path(_R)
        with open(root / "out" / "metrics.json", "r") as f:
            metrics = json.load(f)
        with open(root / "out" / "panel.json", "r") as f:
            panel = json.load(f)
        with open(root / "forecasts.json", "r") as f:
            forecasts = json.load(f)
        with open(root / "tripwires.json", "r") as f:
            tripwires = json.load(f)
        
        with open(os.path.join(out_dir, "metrics.json"), "w") as f:
            json.dump(metrics, f)
        with open(os.path.join(out_dir, "panel.json"), "w") as f:
            json.dump(panel, f)
        with open(os.path.join(tmpdir, "forecasts.json"), "w") as f:
            json.dump(forecasts, f)
        with open(os.path.join(tmpdir, "tripwires.json"), "w") as f:
            json.dump(tripwires, f)
        
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                dashboard.build()
            
            html_path = os.path.join(out_dir, "index.html")
            with open(html_path, "r") as f:
                html = f.read()
            
            # Test hero tiles
            hero_pattern = r'<div class="hero"><div class="l">(.*?)</div><div class="n">(.*?)</div></div>'
            heroes = re.findall(hero_pattern, html)
            
            # Expected values computed from metrics
            expected = [
                ("App fees, last 365 days", f"${metrics['apps']['fees_usd_365d']/1e6:,.1f}M"),
                ("NEAR Intents share of app fees, last 30 days", f"{metrics['apps']['intents_share_30d']*100:.0f}%"),
                ("Active accounts, 30-day average vs a year ago", f"{metrics['active']['yoy_pct']:+.0f}%"),
            ]
            
            assert len(heroes) == 3, f"dashboard.py: expected 3 hero tiles, found {len(heroes)}"
            
            for i, (found, expect) in enumerate(zip(heroes, expected)):
                assert found[0] == expect[0], f"dashboard.py: hero tile {i} label mismatch: got '{found[0]}', expected '{expect[0]}'"
                assert found[1] == expect[1], f"dashboard.py: hero tile {i} value mismatch: got '{found[1]}', expected '{expect[1]}'"
            
            # Verify thesis sentence appears before heroes
            thesis_pattern = r'<p class="thesis"><b>(.*?)</b></p>'
            thesis_match = re.search(thesis_pattern, html)
            assert thesis_match is not None, "dashboard.py: missing thesis sentence in <p class=\"thesis\">"
            
            thesis_text = thesis_match.group(1)
            expected_thesis = "NEAR is a one-product network priced for that product to keep compounding."
            assert thesis_text == expected_thesis, f"dashboard.py: thesis mismatch: got '{thesis_text}', expected '{expected_thesis}'"
            
            # Verify thesis appears before first class="kpi"
            thesis_pos = html.find('<p class="thesis">')
            first_kpi_pos = html.find('class="kpi"')
            assert thesis_pos < first_kpi_pos, "dashboard.py: thesis should appear before KPI tiles"
            
            # Count KPI tiles
            kpi_count = html.count('class="kpi"')
            assert kpi_count == 12, f"dashboard.py: expected 12 KPI tiles, found {kpi_count}"
            
        finally:
            os.chdir(old_cwd)
    finally:
        shutil.rmtree(tmpdir)

def test_dark_theme_and_mobile():
    """dashboard.py: test page uses dark theme colors, no prefers-color-scheme, and responsive width"""
    import dashboard
    
    tmpdir = tempfile.mkdtemp()
    try:
        out_dir = os.path.join(tmpdir, "out")
        os.makedirs(out_dir)
        
        root = pathlib.Path(_R)
        with open(root / "out" / "metrics.json", "r") as f:
            metrics = json.load(f)
        with open(root / "out" / "panel.json", "r") as f:
            panel = json.load(f)
        
        with open(os.path.join(out_dir, "metrics.json"), "w") as f:
            json.dump(metrics, f)
        with open(os.path.join(out_dir, "panel.json"), "w") as f:
            json.dump(panel, f)
        
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                dashboard.build()
            
            html_path = os.path.join(out_dir, "index.html")
            with open(html_path, "r") as f:
                html = f.read()
            
            # Check for dark theme colors
            assert "#0b0f14" in html, "dashboard.py: missing dark background color #0b0f14"
            assert "#00ec97" in html, "dashboard.py: missing accent color #00ec97"
            
            # Check no light/dark media query
            assert "prefers-color-scheme" not in html, "dashboard.py: page should not use prefers-color-scheme media query"
            
            # Check for responsive width
            assert "max-width" in html.lower(), "dashboard.py: missing max-width for responsive design"
            
            # Verify dark colors appear in style
            style_pattern = r'<style>(.*?)</style>'
            style_match = re.search(style_pattern, html, re.DOTALL)
            assert style_match is not None, "dashboard.py: missing <style> block"
            
            style = style_match.group(1)
            # Should define dark colors directly, not through CSS variables for light/dark
            assert "#0b0f14" in style, "dashboard.py: style missing #0b0f14 color definition"
            assert "#00ec97" in style, "dashboard.py: style missing #00ec97 color definition"
            
        finally:
            os.chdir(old_cwd)
    finally:
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    test_every_chart_has_sentence_and_method()
    test_hero_tiles_exact_values()
    test_dark_theme_and_mobile()
    print("PASS")
