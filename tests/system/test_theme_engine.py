# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

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

THEME_IDS = [
    "default",
    "forge",
    "oldgrowth",
    "aurora",
    "tide",
    "unicorn",
    "bloom",
    "tectonic",
    "glacier",
    "reactor",
    "hyperspace",
    "mainframe",
    "grid",
    "stormfront",
    "emberdrift",
    "resonance",
    "inkwash",
    "arcade",
    "ash",
    "deepsea",
    "echo",
    "loom",
    "prism",
    "pulse",
    "solarflare",
    "static",
    "vinyl",
]
THEME_SCRIPTS = [
    "/static/js/theme/theme-registry.js",
    "/static/js/theme/effect-level.js",
    "/static/js/theme/signal-bus.js",
    "/static/js/theme/theme-manager.js",
]
THEME_REGISTRATIONS = [f"/static/js/themes/{t}.js" for t in THEME_IDS]

# Themes that ship a CSS layer (every theme except the cosmetic `default`).
THEME_CSS_LAYERS = [t for t in THEME_IDS if t != "default"]


class TestThemeAssets:
    """ST-T1: All theme engine JS and CSS assets resolve."""

    ALL_ASSETS = (
        THEME_SCRIPTS
        + THEME_REGISTRATIONS
        + [f"/static/css/themes/{t}.css" for t in THEME_CSS_LAYERS]
    )

    @pytest.mark.parametrize("path", ALL_ASSETS)
    def test_theme_assets_resolve(self, client: httpx.Client, path: str) -> None:
        resp = client.get(path)
        assert (
            resp.status_code == 200
        ), f"Theme asset {path} returned {resp.status_code}"


class TestThemePageIntegration:
    """ST-T2: The default page includes theme engine wiring."""

    def test_fouc_script_present(self, client: httpx.Client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        assert "data-skin" in html, "FOUC script missing data-skin attribute setter"
        assert "data-theme" in html, "FOUC script missing data-theme attribute setter"
        assert (
            "theme-layer-css" in html
        ), "FOUC script missing theme-layer-css link injection"

    def test_theme_engine_scripts_load(self, client: httpx.Client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        html = resp.text
        for script in THEME_SCRIPTS:
            assert (
                script in html
            ), f"Theme engine script {script} not referenced in page"

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
        assert (
            "theme-reduce-effects" in html
        ), "Reduce effects control missing from picker"
        assert "theme-audio-optin" in html, "Audio opt-in control missing from picker"


class TestPickerKeyboardNavigation:
    """ST-T4: The theme manager ships the grid keyboard-navigation + preview logic.

    The picker grid/items are rendered client-side, so we assert the behavior is
    present in the shipped ``theme-manager.js`` asset rather than in served HTML.
    """

    def test_manager_implements_arrow_navigation(self, client: httpx.Client) -> None:
        js = client.get("/static/js/theme/theme-manager.js").text
        for token in ("ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown"):
            assert (
                token in js
            ), f"theme-manager.js missing arrow-key handler for {token}"
        assert "Enter" in js, "theme-manager.js missing Enter-to-commit handling"
        assert "Escape" in js, "theme-manager.js missing Escape-to-cancel handling"

    def test_manager_has_live_preview_without_persist(
        self, client: httpx.Client
    ) -> None:
        js = client.get("/static/js/theme/theme-manager.js").text
        assert "previewApply" in js, "theme-manager.js missing live-preview function"
        assert "persist: false" in js, "preview must apply without persisting"
        assert (
            "commitSelection" in js
        ), "theme-manager.js missing commit-on-Enter function"

    def test_manager_builds_scrollable_grid(self, client: httpx.Client) -> None:
        js = client.get("/static/js/theme/theme-manager.js").text
        assert "theme-picker__grid" in js, "picker should render a grid container"
        css = client.get("/static/css/base.css").text
        assert ".theme-picker__grid" in css, "base.css missing grid rule"
        assert "overflow-y: auto" in css, "picker grid must scroll when list is long"


class TestThemeCssFiles:
    """ST-T3: Theme CSS files exist in the container."""

    @pytest.mark.parametrize("theme", THEME_CSS_LAYERS)
    def test_theme_css_layer_exists_in_container(self, theme: str) -> None:
        result = compose_exec(
            f"test -f /anvil/api/static/css/themes/{theme}.css && echo FOUND"
        )
        assert (
            result.returncode == 0 and "FOUND" in result.stdout
        ), f"Theme CSS {theme}.css not found in container"
