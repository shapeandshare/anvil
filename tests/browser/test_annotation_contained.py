"""Playwright e2e tests for contained element capture in annotations.

Verifies that element annotations capture details of elements within the
bounding box (including partial overlaps), exclude script/style/hidden
elements, and include spatial data (relX, relY, width, height, overlapRatio).

Also includes regression tests for annotation toggle lifecycle bugs:
- Bug 1 (toggle-cycle): _unbindEvents() was never called in
  _exitAnnotationMode(), causing orphaned event listeners to accumulate
  across enter/exit cycles.
- Bug 2 (manage-popup): _showManagePopup() referenced an undefined `popup`
  variable, causing a ReferenceError when re-clicking an already-annotated
  element.
- Bug 3 (feedback-page exclusion): base.html excluded /v1/feedback-page
  from annotation mode initialization; only /login should be excluded.
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


@pytest.mark.usefixtures("_readiness_check")
class TestAnnotationToggleRegression:
    """Regression tests for annotation toggle lifecycle bugs.

    These are characterization tests that guard against three bugs fixed
    in annotation.js:

    1. ``_unbindEvents()`` was never called in ``_exitAnnotationMode()``,
       causing orphaned event listeners to accumulate across enter/exit
       cycles. After the fix, ``_unbindEvents()`` is the first line of
       ``_exitAnnotationMode()``.

    2. ``_showManagePopup()`` referenced an undefined ``popup`` variable
       (ReferenceError when re-clicking an already-annotated element).
       After the fix, the popup element is created and
       ``_manageAnnotations`` is set before ``_buildManageList()``.

    3. ``base.html`` excluded ``/v1/feedback-page`` from annotation mode
       initialization (only ``/login`` should be excluded). After the fix,
       ``window._annotationCanvas`` is defined on the feedback page.
    """

    TIMEOUT = 15_000

    def test_toggle_cycle_does_not_leak_events(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Enter/exit/re-enter annotation mode without event listener
        leaks or stale overlay state.
        """
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEST_ROUTE}")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""() => {
            var canvas = window._annotationCanvas;
            if (!canvas) return { error: 'No annotation canvas found' };

            // First enter — create overlay
            canvas._enterAnnotationMode();
            var overlay1 = canvas._overlayEl;
            var overlay1InDom = overlay1 && overlay1.parentNode === document.body;

            // Exit — remove overlay and unbind events
            canvas._exitAnnotationMode(true);
            var overlay1Removed = !overlay1 || !overlay1.parentNode;

            // Re-enter — should create a new overlay, not reuse stale one
            canvas._enterAnnotationMode();
            var overlay2 = canvas._overlayEl;
            var overlay2InDom = overlay2 && overlay2.parentNode === document.body;
            var isNewOverlay = overlay1 !== overlay2;

            // Verify tool setting works after re-enter
            canvas.setTool('element');
            var toolSet = canvas._activeTool === 'element';

            // Clean up
            canvas._exitAnnotationMode(true);

            return {
                overlay1Created: overlay1InDom,
                overlay1Removed: overlay1Removed,
                overlay2Created: overlay2InDom,
                isNewOverlay: isNewOverlay,
                toolSet: toolSet,
            };
        }""")

        assert result.get("error") is None, result.get("error", "")
        assert result["overlay1Created"], "First enter should create overlay"
        assert result["overlay1Removed"], "Exit should remove overlay"
        assert result["overlay2Created"], "Re-enter should create new overlay"
        assert result[
            "isNewOverlay"
        ], "Should create new overlay instance, not reuse stale one"
        assert result["toolSet"], "Should be able to set tool after re-enter"

        checker.assert_no_errors()

    def test_manage_popup_handles_existing_annotations(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Re-clicking an annotated element shows manage popup without
        ReferenceError.
        """
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEST_ROUTE}")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""() => {
            var canvas = window._annotationCanvas;
            if (!canvas) return { error: 'No annotation canvas found' };

            canvas._enterAnnotationMode();

            // Create a test element
            var el = document.createElement('div');
            el.id = 'manage-popup-test-el';
            el.style.cssText = (
                'width:200px;height:100px;margin:100px;background:red;'
            );
            document.body.appendChild(el);

            var rect = el.getBoundingClientRect();
            var selector = '#' + el.id;
            var elementInfo = {
                tagName: 'div', id: el.id, className: '',
                textContent: '', outerHTML: el.outerHTML,
                selector: selector, attributes: {}
            };

            // Push an annotation with matching selector so the manage
            // popup code path is exercised
            canvas._annotations.push({
                type: 'element',
                note: 'Test annotation',
                data: {
                    x: Math.round(rect.left),
                    y: Math.round(rect.top),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    selector: selector,
                    elementInfo: elementInfo,
                    containedElements: []
                }
            });

            // Call _showManagePopup — this is the method that had the
            // undefined `popup` variable bug
            var matchingAnnotations = [
                { index: 0, annotation: canvas._annotations[0] }
            ];
            var popupX = rect.left + rect.width + 10;
            var popupY = rect.top;
            canvas._showManagePopup(
                popupX, popupY, matchingAnnotations,
                rect, selector, elementInfo
            );

            // Check that popup was created and is in the DOM
            var popupEl = canvas._notePopup;
            var popupInDom = popupEl && popupEl.parentNode !== null;
            var popupClass = popupEl ? popupEl.className : '';

            // Verify _manageAnnotations was set before _buildManageList
            // (was the second bug — used before assignment)
            var manageAnnotationsSet = (
                Array.isArray(canvas._manageAnnotations)
                && canvas._manageAnnotations.length > 0
            );

            // Clean up
            el.remove();
            canvas._exitAnnotationMode(true);

            return {
                popupCreated: popupEl !== null,
                popupInDom: popupInDom,
                popupClass: popupClass,
                manageAnnotationsSet: manageAnnotationsSet,
            };
        }""")

        assert result.get("error") is None, result.get("error", "")
        assert result["popupCreated"], "Should create popup element"
        assert result["popupInDom"], "Popup should be in the DOM"
        assert (
            "feedback-note-popup" in result["popupClass"]
        ), "Popup should have correct class name"
        assert result[
            "manageAnnotationsSet"
        ], "_manageAnnotations should be set before _buildManageList"

        checker.assert_no_errors()

    def test_feedback_page_has_annotation_canvas(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Annotation canvas is initialized on /v1/feedback-page.

        Regression: base.html previously excluded /v1/feedback-page from
        annotation mode initialization. Only /login should be excluded.
        """
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/feedback-page")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""() => {
            var canvas = window._annotationCanvas;
            var toggleBtn = document.getElementById('feedback-toggle-btn');
            var reportList = document.getElementById('feedback-report-list');
            var emptyState = document.getElementById('feedback-empty-state');

            if (!canvas) return { canvasDefined: false };

            // Enter annotation mode on the feedback page to verify the
            // full lifecycle works
            canvas._enterAnnotationMode();
            var overlayCreated = (
                canvas._overlayEl
                && canvas._overlayEl.parentNode === document.body
            );

            // Exit cleanly
            canvas._exitAnnotationMode(true);
            var overlayRemoved = (
                !canvas._overlayEl || !canvas._overlayEl.parentNode
            );

            return {
                canvasDefined: true,
                toggleBtnExists: toggleBtn !== null,
                reportListExists: reportList !== null,
                emptyStateExists: emptyState !== null,
                overlayCreated: overlayCreated,
                overlayRemoved: overlayRemoved,
            };
        }""")

        assert result[
            "canvasDefined"
        ], "Annotation canvas should be defined on /v1/feedback-page"
        assert result["toggleBtnExists"], "Toggle button should exist on feedback page"
        assert result[
            "reportListExists"
        ], "Feedback report list should still be present"
        assert result[
            "emptyStateExists"
        ], "Feedback empty state should still be present"
        assert result[
            "overlayCreated"
        ], "Should be able to enter annotation mode on feedback page"
        assert result[
            "overlayRemoved"
        ], "Should be able to exit annotation mode on feedback page"

        checker.assert_no_errors()

    def test_toggle_cycle_rebinds_events_correctly(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Enter/exit/re-enter annotation mode, then verify hover-highlight
        mechanism activates on a real element after re-entry.

        Regression for Bug A: ``_unbindEvents()`` was never called in
        ``_exitAnnotationMode()``, causing orphaned event listeners across
        enter/exit cycles. After the fix, re-entering produces a clean
        overlay with working hover-highlight.
        """
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEST_ROUTE}")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""() => {
            var canvas = window._annotationCanvas;
            if (!canvas) return { error: 'No annotation canvas found' };

            // ── First enter ──
            canvas._enterAnnotationMode();
            var overlay1 = canvas._overlayEl;
            var overlay1InDom = overlay1 && overlay1.parentNode === document.body;

            // ── Exit ──
            canvas._exitAnnotationMode(true);
            var overlay1Removed = !overlay1 || !overlay1.parentNode;

            // ── Re-enter ──
            canvas._enterAnnotationMode();
            var overlay2 = canvas._overlayEl;
            var overlay2InDom = overlay2 && overlay2.parentNode === document.body;
            var isNewOverlay = overlay1 !== overlay2;

            // Set element tool so hover highlight engages
            canvas.setTool('element');

            // Create a positioned element in the DOM. Uses
            // position:fixed with a very high z-index (not
            // position:absolute) because the app shell (.app-shell)
            // has position:relative;z-index:2 -- a plain
            // absolutely-positioned body child with a low z-index
            // loses that stacking comparison and would be hit-tested
            // *behind* the app content, causing elementFromPoint to
            // resolve to page content instead of this element.
            var el = document.createElement('div');
            el.id = 'hover-highlight-target';
            el.style.cssText = (
                'width:200px;height:100px;'
                + 'position:fixed;top:200px;left:200px;'
                + 'background:red;z-index:999999;'
            );
            document.body.appendChild(el);
            var rect = el.getBoundingClientRect();

            // Dispatch a mousemove event over the element to trigger
            // _updateHoverHighlight
            var centerX = rect.left + rect.width / 2;
            var centerY = rect.top + rect.height / 2;
            var hoverEvent = new MouseEvent('mousemove', {
                clientX: centerX,
                clientY: centerY,
                bubbles: true,
            });
            canvas._overlayEl.dispatchEvent(hoverEvent);

            // Check hover-highlight state
            var hl = canvas._hoverHighlightEl;
            var hlDisplayed = hl && hl.style.display !== 'none';
            var hlLeft = hl ? Math.round(parseFloat(hl.style.left)) : -1;
            var hlTop = hl ? Math.round(parseFloat(hl.style.top)) : -1;
            var hlWidth = hl ? Math.round(parseFloat(hl.style.width)) : -1;
            var hlHeight = hl ? Math.round(parseFloat(hl.style.height)) : -1;
            // Confirm the highlight box actually matches OUR target
            // element's rect (not some unrelated page element that
            // happened to be under the cursor).
            var matchesTarget = (
                hlDisplayed
                && Math.abs(hlLeft - rect.left) <= 2
                && Math.abs(hlTop - rect.top) <= 2
                && Math.abs(hlWidth - rect.width) <= 2
                && Math.abs(hlHeight - rect.height) <= 2
            );

            // Clean up
            el.remove();
            canvas._exitAnnotationMode(true);

            return {
                overlay1Created: overlay1InDom,
                overlay1Removed: overlay1Removed,
                overlay2Created: overlay2InDom,
                isNewOverlay: isNewOverlay,
                hlDisplayed: hlDisplayed,
                hlLeft: hlLeft,
                hlTop: hlTop,
                hlWidth: hlWidth,
                hlHeight: hlHeight,
                matchesTarget: matchesTarget,
            };
        }""")

        assert result.get("error") is None, result.get("error", "")
        assert result["overlay1Created"], "First enter should create overlay"
        assert result["overlay1Removed"], "Exit should remove overlay"
        assert result["overlay2Created"], "Re-enter should create new overlay"
        assert result[
            "isNewOverlay"
        ], "Should create new overlay instance, not reuse stale one"
        assert result[
            "hlDisplayed"
        ], "Hover highlight should be displayed after re-enter + mousemove"
        assert (
            result["hlWidth"] >= 1
        ), "Hover highlight should have positive width: got " + str(result["hlWidth"])
        assert result["matchesTarget"], (
            "Hover highlight should match the target element's rect, "
            "confirming the overlay's hit-testing (via "
            "_getElementUnderCursor) resolved to our synthetic "
            "element rather than an unrelated page element"
        )
        assert (
            result["hlHeight"] >= 1
        ), "Hover highlight should have positive height: got " + str(result["hlHeight"])

        checker.assert_no_errors()

    def test_manage_popup_no_reference_error(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Re-clicking an already-annotated element (via _onOverlayClick)
        triggers _showManagePopup without ReferenceError.

        Regression for Bug B: ``_showManagePopup()`` referenced an
        undefined ``popup`` variable. After the fix, the popup element
        is properly created and ``_manageAnnotations`` is set before
        ``_buildManageList()``.
        """
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}{TEST_ROUTE}")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""() => {
            var canvas = window._annotationCanvas;
            if (!canvas) return { error: 'No annotation canvas found' };

            canvas._enterAnnotationMode();
            canvas.setTool('element');

            // Create a test element. Uses position:fixed with a very
            // high z-index (not position:absolute) because the app
            // shell (.app-shell) has position:relative;z-index:2 --
            // a plain absolutely-positioned body child with a low
            // z-index loses that stacking comparison and would be
            // hit-tested *behind* the app content, causing
            // elementFromPoint to resolve to page content instead of
            // this synthetic element.
            var el = document.createElement('div');
            el.id = 'manage-click-target';
            el.style.cssText = (
                'width:200px;height:100px;'
                + 'position:fixed;top:200px;left:200px;'
                + 'background:green;z-index:999999;'
            );
            document.body.appendChild(el);
            var rect = el.getBoundingClientRect();

            // Pre-populate an annotation matching this element's selector
            canvas._annotations.push({
                type: 'element',
                note: 'Bug B regression annotation',
                data: {
                    x: Math.round(rect.left),
                    y: Math.round(rect.top),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    selector: '#manage-click-target',
                    elementInfo: {
                        tagName: 'div',
                        id: 'manage-click-target',
                        className: '',
                        textContent: '',
                        outerHTML: el.outerHTML,
                        selector: '#manage-click-target',
                        attributes: {},
                    },
                    containedElements: [],
                }
            });

            // Simulate a click on the overlay at the element's position,
            // which should match the existing annotation and trigger
            // _showManagePopup (the bug B code path)
            var centerX = rect.left + rect.width / 2;
            var centerY = rect.top + rect.height / 2;
            var clickEvent = new MouseEvent('click', {
                clientX: centerX,
                clientY: centerY,
                bubbles: true,
            });
            canvas._overlayEl.dispatchEvent(clickEvent);

            // Check manage popup state
            var popupEl = canvas._notePopup;
            var popupInDom = popupEl && popupEl.parentNode !== null;
            var popupClass = popupEl ? popupEl.className : '';
            var popupContent = popupEl ? popupEl.textContent || '' : '';
            var contentIsDefined = (
                popupContent.length > 0
                && popupContent !== 'undefined'
                && popupContent !== 'null'
            );
            var manageAnnotationsSet = (
                Array.isArray(canvas._manageAnnotations)
                && canvas._manageAnnotations.length > 0
            );

            // Clean up
            el.remove();
            canvas._exitAnnotationMode(true);

            return {
                popupCreated: popupEl !== null,
                popupInDom: popupInDom,
                popupClass: popupClass,
                contentDefined: contentIsDefined,
                manageAnnotationsSet: manageAnnotationsSet,
            };
        }""")

        assert result.get("error") is None, result.get("error", "")
        assert result["popupCreated"], "Should create popup element"
        assert result["popupInDom"], "Popup should be in the DOM"
        assert (
            "feedback-note-popup" in result["popupClass"]
        ), "Popup should have correct class name"
        assert result[
            "contentDefined"
        ], "Popup should have defined (non-undefined) content"
        assert result[
            "manageAnnotationsSet"
        ], "_manageAnnotations should be set before _buildManageList"

        checker.assert_no_errors()

    def test_feedback_page_annotation_enabled(
        self,
        page,
        base_url: str,
        assert_no_console_errors,
    ) -> None:
        """Annotation mode is fully functional on /v1/feedback-page,
        accessible via the toggle button click.

        Regression for Bug C: base.html previously excluded
        /v1/feedback-page from annotation mode initialization (only
        /login should be excluded). After the fix,
        window._annotationCanvas is defined, the toggle button is
        clickable, and the feedback page's own report-management UI
        remains visible after entering annotation mode.
        """
        checker = assert_no_console_errors(page)
        page.goto(f"{base_url}/v1/feedback-page")
        page.wait_for_load_state("networkidle")

        result = page.evaluate("""() => {
            var canvas = window._annotationCanvas;
            var toggleBtn = document.getElementById('feedback-toggle-btn');

            if (!canvas) return { canvasDefined: false };
            if (!toggleBtn) return {
                canvasDefined: true,
                toggleBtnExists: false,
            };

            // Click toggle button to enter annotation mode
            toggleBtn.click();

            var overlayCreated = (
                canvas._overlayEl
                && canvas._overlayEl.parentNode === document.body
            );

            // Verify feedback page UI is still visible
            var reportList = document.getElementById('feedback-report-list');
            var listVisible = reportList
                && reportList.style.display !== 'none'
                && reportList.offsetParent !== null;

            var detailCard = document.getElementById('feedback-detail-card');
            var detailVisible = detailCard
                && detailCard.style.display !== 'none';

            // Click toggle again to exit annotation mode
            toggleBtn.click();

            var overlayRemoved = (
                !canvas._overlayEl || !canvas._overlayEl.parentNode
            );

            return {
                canvasDefined: true,
                toggleBtnExists: true,
                overlayCreated: overlayCreated,
                overlayRemoved: overlayRemoved,
                reportListVisible: listVisible,
            };
        }""")

        assert result[
            "canvasDefined"
        ], "Annotation canvas should be defined on /v1/feedback-page"
        assert result["toggleBtnExists"], "Toggle button should exist on feedback page"
        assert result[
            "overlayCreated"
        ], "Toggle button click should enter annotation mode"
        assert result[
            "overlayRemoved"
        ], "Second toggle click should exit annotation mode"
        assert result[
            "reportListVisible"
        ], "Feedback report list should remain visible in annotation mode"

        checker.assert_no_errors()
