# Contract: ScrollScene Primitive

## Purpose
Reusable scroll-driven page template: sticky visualization pane + scrolling narrative column. Each Step entering the viewport drives the pinned visual's state.

## Interface

```javascript
// ScrollScene manages one pinned visual + N steps
class ScrollScene {
  constructor(options: ScrollSceneOptions);
  
  // Currently active step key
  get activeStep(): string;
  
  // Add observer for a step element
  observeStep(key: string, element: HTMLElement): void;
  
  // Remove observer (cleanup)
  unobserveStep(key: string): void;
  
  // Destroy all observers
  destroy(): void;
  
  // Called when active step changes
  onstepchange: (key: string) => void;
}

interface ScrollSceneOptions {
  container: HTMLElement;     // ScrollScene wrapper element
  pinnedVisual: HTMLElement;  // Sticky visual pane
  initialStep?: string;       // Step key to activate on mount (default: first)
  threshold?: number;         // IntersectionObserver threshold (default: 0.5)
  rootMargin?: string;        // IntersectionObserver rootMargin (default: '0px')
}
```

## Step Contract

```html
<!-- Each Step in the narrative column -->
<div class="step" data-step-key="tokenization-intro">
  <h2>How Tokenization Works</h2>
  <p>Every word gets split into tokens...</p>
  <!-- Optional interactive widget -->
  <div class="concept-widget" data-widget="tokenization"></div>
</div>
```

## Behavior

1. On mount, `ScrollScene` creates an `IntersectionObserver` with specified threshold/rootMargin
2. Each `.step[data-step-key]` element is observed
3. When a step crosses the threshold into viewport, `onstepchange(key)` fires with that step's key
4. `pinnedVisual` re-renders based on `key` (consumer's responsibility)
5. On unmount, `destroy()` disconnects the observer

## Mobile Collapse

- At `max-width: 768px`, `pinnedVisual` loses `position: sticky` and renders inline
- Each step's visual state renders adjacent to its corresponding step text
- IntersectionObserver behavior is unchanged; visual still updates

## Reduced Motion

- Under `prefers-reduced-motion`, state changes on `pinnedVisual` are instant (no CSS transitions)
- IntersectionObserver thresholds remain — state still updates, just without animation

## Acceptance

- [ ] One `ScrollScene` + one IntersectionObserver per page; all concept pages use the same primitive
- [ ] Adding/reordering concepts = adding/reordering `.step` divs, no new scroll logic
- [ ] IntersectionObserver disconnected on unmount (no scroll-handler leaks)
- [ ] Mobile: visual collapses inline at 768px breakpoint
- [ ] Reduced motion: state transitions are instant