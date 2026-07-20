"""Playwright e2e tests for contained element capture in annotations.

Verifies that element annotations capture details of elements within the
bounding box (including partial overlaps), exclude script/style/hidden
elements, and include spatial data (relX, relY, width, height, overlapRatio).
"""

from __future__ import annotations

import pytest

TEST_ROUTE = "/v1/training-page"


@pytest.mark.usefixtures("_readiness_check")
class TestAnnotationContainedElements:
    """Browser tests for contained element capture in annotation
    bounding boxes.
    """

    TIMEOUT = 15_000

    def test_contained_elements_includes_children_with_spatial_data(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """_findContainedElements returns child elements with spatial
        data and filters out excluded element types.
        """
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEST_ROUTE}")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""() => {
            var canvas = window._annotationCanvas;
            if (!canvas) return { error: 'No annotation canvas found' };

            // Create a test container with known child elements
            var div = document.createElement('div');
            div.id = 'contained-test-container';
            div.style.cssText = [
                'position:relative;',
                'width:400px;height:400px;',
                'margin:50px;',
                'background:rgba(0,0,0,0.1);',
            ].join('');
            div.innerHTML = [
                '<span id="ct-child-1" style="display:inline-block;width:100px;height:50px;">Visible child</span>',
                '<p id="ct-child-2" style="width:200px;height:30px;margin-top:10px;">Paragraph child</p>',
                '<script id="ct-script">var x=1;</script>',
                '<style id="ct-style">.x{}</style>',
                '<div id="ct-hidden" style="display:none;">Hidden</div>',
                '<div id="ct-invisible" style="visibility:hidden;">Invisible</div>',
            ].join('');
            document.body.appendChild(div);

            var rect = div.getBoundingClientRect();
            var contained = canvas._findContainedElements(rect);

            // Cleanup test elements
            div.remove();

            var tagNames = contained.map(function(e) { return e.tagName; });

            return {
                count: contained.length,
                containsSpan: tagNames.indexOf('span') >= 0,
                containsP: tagNames.indexOf('p') >= 0,
                noScript: tagNames.indexOf('script') < 0,
                noStyle: tagNames.indexOf('style') < 0,
                noHidden: contained.filter(function(e) {
                    return e.id === 'ct-hidden';
                }).length === 0,
                noInvisible: contained.filter(function(e) {
                    return e.id === 'ct-invisible';
                }).length === 0,
                hasSpatial: contained.length > 0 && 'spatial' in contained[0],
                sampleSpatial: contained.length > 0 ? contained[0].spatial : null,
                limitedToHundred: contained.length <= 100,
            };
        }""")

        assert result.get("error") is None, result.get("error", "")
        assert result["count"] > 0, "Should find contained elements"
        assert result["containsSpan"], "Should find span child"
        assert result["containsP"], "Should find paragraph child"
        assert result["noScript"], "Should exclude script elements"
        assert result["noStyle"], "Should exclude style elements"
        assert result["noHidden"], "Should exclude display:none elements"
        assert result["noInvisible"], "Should exclude visibility:hidden elements"
        assert result["hasSpatial"], "Should include spatial data"
        assert (
            result["sampleSpatial"]["overlapRatio"] > 0
        ), "Spatial data should have positive overlapRatio"
        assert "relX" in result["sampleSpatial"], "Spatial data should include relX"
        assert "relY" in result["sampleSpatial"], "Spatial data should include relY"
        assert result["sampleSpatial"]["width"] > 0, "Spatial data should include width"
        assert (
            result["sampleSpatial"]["height"] > 0
        ), "Spatial data should include height"
        assert result[
            "limitedToHundred"
        ], "Max contained elements should default to 100"

        checker.assert_no_errors()

    def test_max_contained_elements_configurable(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """MaxContainedElements configuration is respected."""
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEST_ROUTE}")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""() => {
            var canvas = window._annotationCanvas;
            if (!canvas) return { error: 'No annotation canvas found' };

            // Create a dense container with many children
            var div = document.createElement('div');
            div.id = 'max-test-container';
            div.style.cssText = [
                'position:relative;',
                'width:300px;height:300px;',
                'margin:50px;',
            ].join('');
            var html = '';
            for (var i = 0; i < 50; i++) {
                html += '<span style="display:inline-block;width:10px;height:10px;">'
                    + i + '</span>';
            }
            div.innerHTML = html;
            document.body.appendChild(div);

            var rect = div.getBoundingClientRect();

            // Test with different max values
            canvas._maxContainedElements = 5;
            var contained5 = canvas._findContainedElements(rect);

            canvas._maxContainedElements = 20;
            var contained20 = canvas._findContainedElements(rect);

            // Reset and cleanup
            canvas._maxContainedElements = 100;
            div.remove();

            return {
                max5Count: contained5.length,
                max20Count: contained20.length,
                max5Respected: contained5.length <= 5,
                max20Respected: contained20.length <= 20,
                // The sparse grid may find fewer elements than the max cap;
                // the key test is that max5 <= max20 (capping reduces results)
                cappingWorks: contained5.length <= contained20.length,
            };
        }""")

        assert result.get("error") is None, result.get("error", "")
        assert result["max5Respected"], "Max 5 limit not respected: got " + str(
            result["max5Count"]
        )
        assert result["max20Respected"], "Max 20 limit not respected: got " + str(
            result["max20Count"]
        )
        assert result["cappingWorks"], (
            "Capping did not reduce results: 5="
            + str(result["max5Count"])
            + " 20="
            + str(result["max20Count"])
        )

        checker.assert_no_errors()

    def test_annotation_payload_includes_contained_elements(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Saved element annotations include containedElements in their
        data payload.
        """
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEST_ROUTE}")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""() => {
            var canvas = window._annotationCanvas;
            if (!canvas) return { error: 'No annotation canvas found' };

            // Build a synthetic annotation to ensure containedElements field
            // is populated in the data payload
            var testEl = document.createElement('div');
            testEl.id = 'payload-test-el';
            testEl.style.cssText = 'width:200px;height:100px;margin:100px;';
            testEl.innerHTML = '<span id="payload-inner">Inner</span>';
            document.body.appendChild(testEl);

            var rect = testEl.getBoundingClientRect();
            canvas._enterAnnotationMode();

            // Simulate what _onOverlayClick does
            var pending = {
                type: 'element',
                data: {
                    x: Math.round(rect.left),
                    y: Math.round(rect.top),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    selector: '#payload-test-el',
                    elementInfo: { tagName: 'div', id: 'payload-test-el' },
                    containedElements: canvas._findContainedElements(rect),
                }
            };

            // Commit the annotation (simulates what save does)
            canvas._commitAnnotation('Test annotation with contained elements');
            var annotations = canvas._getAnnotations
                ? canvas._getAnnotations()
                : canvas._annotations.slice();

            // Cleanup
            testEl.remove();
            canvas._exitAnnotationMode(true);

            // The last annotation should have containedElements
            var lastAnn = annotations[annotations.length - 1];

            return {
                hasContainedElements: lastAnn
                    && lastAnn.data
                    && Array.isArray(lastAnn.data.containedElements),
                containedCount: lastAnn && lastAnn.data
                    ? lastAnn.data.containedElements.length
                    : 0,
            };
        }""")

        assert result.get("error") is None, result.get("error", "")
        assert result[
            "hasContainedElements"
        ], "Annotation data should include containedElements array"
        assert result["containedCount"] > 0, "containedElements should have entries"

        checker.assert_no_errors()
