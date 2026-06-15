# wizard-tabs Reuse Pattern

The `wizard-tabs` CSS classes in `archetypes.css` define a generic tabbed panel pattern that can be reused anywhere in the UI.

## Structure

```html
<div class="wizard-tabs">
  <button class="wizard-tab wizard-tab--active" data-tab="tab-panel-id">Tab Label</button>
  <button class="wizard-tab" data-tab="tab-other-panel">Other Tab</button>
</div>

<div class="wizard-panel wizard-panel--active" id="tab-panel-id">...</div>
<div class="wizard-panel" id="tab-other-panel">...</div>
```

## JS Pattern

```js
function switchTab(tabId) {
  document.querySelectorAll('.wizard-tabs .wizard-tab').forEach(function(tab) {
    tab.classList.toggle('wizard-tab--active', tab.getAttribute('data-tab') === tabId);
  });
  document.querySelectorAll('.wizard-panel').forEach(function(panel) {
    panel.classList.toggle('wizard-panel--active', panel.id === tabId);
  });
}
```

## CSS Key Properties

| Class | Role |
|-------|------|
| `.wizard-tabs` | Flex container for tab buttons, bottom border separator |
| `.wizard-tab` | Pill-shaped button, `text-tertiary` when inactive |
| `.wizard-tab--active` | Blue (`--accent`) filled pill, white text |
| `.wizard-panel` | `display: none` by default |
| `.wizard-panel--active` | `display: block` with slide-in animation |

## Notes

- The `data-tab` attribute value must match the panel `id` exactly
- No extra JS framework needed — vanilla DOM class toggling
- Used on both the training page wizard and the data page manager