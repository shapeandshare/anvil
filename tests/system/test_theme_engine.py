"""System tests for the behavioral theme engine.

These tests run against a running container deployed via docker compose.
They validate: theme file assets resolve, theme engine scripts load, theme
picker markup is present, and the FOUC bootstrap script is inline.

Run via: `make test-system`
"""

import re

import httpx
import pytest

from conftest import compose_exec

THEME_IDS = ["default", "forge", "oldgrowth", "aurora"]
THEME_SCRIPTS = [
    "/static/js/theme/theme-registry.js",
    "/static/js/theme/effect-level.js",
    "/static/js/theme/signal-bus.js",
    "/static/js/theme/theme-manager.js",
]
THEME_REGISTRATIONS = [
    "/static/js/themes/default.js",
    "/static/js/themes/forge.js",
    "/static/js/themes/oldgrowth.js",
    "/static/js/themes/aurora.js",
]


class TestThemeAssets:
    """ST-T1: All theme engine JS and CSS assets resolve."""

    ALL_ASSETS = THEME_SCRIPTS + THEME_REGISTRATIONS + [
        f"/static/css/themes/{t}.css" for t in ("forge", "oldgrowth", "aurora")
    ]

    @pytest.mark.parametrize("path", ALL_ASSETS)
    def test_theme_assets_resolve(self, client: httpx.Client, path: str) -> None:
        resp = client.get(path)
        assert resp.status_code == 200, (
            f"Theme asset {path} returned {resp.status_code}"
        )


class TestThemePageIntegration:
    """ST-T2: The default page includes theme engine wiring."""

    def test_fouc_script_present(self, client: httpx.Client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        assert "data-skin" in html, "FOUC script missing data-skin attribute setter"
        assert "data-theme" in html, "FOUC script missing data-theme attribute setter"
        assert 'theme-layer-css' in html, "FOUC script missing theme-layer-css link injection"

    def test_theme_engine_scripts_load(self, client: httpx.Client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        for script in THEME_SCRIPTS:
            assert script in html, f"Theme engine script {script} not referenced in page"

    def test_theme_registrations_included(self, client: httpx.Client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        for reg in THEME_REGISTRATIONS:
            assert reg in html, f"Theme registration {reg} not referenced in page"

    def test_theme_picker_markup_present(self, client: httpx.Client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        assert 'id="theme-picker"' in html, "Theme picker container not found in page"
        assert 'id="theme-picker-trigger"' in html, "Picker trigger button not found"
        assert 'id="theme-picker-menu"' in html, "Picker menu not found"

    def test_picker_static_structure_present(self, client: httpx.Client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        assert 'id="theme-picker"' in html, "Theme picker wrapper not found"
        assert 'id="theme-picker-menu"' in html, "Picker menu container not found"
        assert 'aria-haspopup="true"' in html, "Picker trigger missing aria-haspopup"

    def test_effect_controls_in_picker(self, client: httpx.Client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        assert "theme-reduce-effects" in html, "Reduce effects control missing from picker"
        assert "theme-audio-optin" in html, "Audio opt-in control missing from picker"


class TestThemeCssFiles:
    """ST-T3: Theme CSS files exist in the container."""

    @pytest.mark.parametrize("theme", ["forge", "oldgrowth", "aurora"])
    def test_theme_css_layer_exists_in_container(self, theme: str) -> None:
        result = compose_exec(
            f"test -f /anvil/api/static/css/themes/{theme}.css && echo FOUND"
        )
        assert result.returncode == 0 and "FOUND" in result.stdout, (
            f"Theme CSS {theme}.css not found in container"
        )