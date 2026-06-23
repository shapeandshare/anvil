# Contract: Chart Primitive (Loss Chart)

## Purpose
A single canvas-based chart component used in two modes:
1. **Live mode** — append-only, SSE-driven, throttled paint
2. **Replay mode** — full dataset rendered immediately on load (no animation)

Same visual primitive, same component, different data source.

## Interface

```javascript
class LossChart {
  constructor(canvas: HTMLCanvasElement, options: ChartOptions);
  
  // Live mode: append a single data point
  appendPoint(point: DataPoint): void;
  
  // Replay mode: set all data at once
  setData(points: DataPoint[]): void;
  
  // Clear canvas
  clear(): void;
  
  // Resize handler (call on container resize)
  resize(): void;
  
  // Destroy — clean up animation frame, remove listeners
  destroy(): void;
}

interface ChartOptions {
  mode: 'live' | 'replay';
  maxPoints?: number;          // Max visible points before downsampling (default: 2000)
  throttleInterval?: number;   // Min ms between paints (default: 50)
  accentColor?: string;        // Line color (default: var(--accent))
  backgroundColor?: string;    // Canvas background (default: var(--surface))
  gridColor?: string;          // Grid line color (default: var(--border))
  textColor?: string;          // Axis label color (default: var(--text-muted))
}

interface DataPoint {
  step: number;
  loss: number;
}
```

## Rendering Pipeline

```
SSE metrics event
  ↓
appendPoint({step, loss})
  ↓
[Throttle gate] — if lastPaint + throttleInterval > now, skip
  ↓
[Downsample gate] — if points.length > maxPoints, apply LTTB
  ↓
[Paint] — clearCanvas → drawGrid → drawAxes → drawLine → drawLabels
  ↓
requestAnimationFrame (or setTimeout for fixed interval)
```

## Downsampling (LTTB — Largest Triangle Three Bucket)

When `points.length > maxPoints`:
1. Divide points into `maxPoints - 2` buckets
2. For each bucket, find the point that forms the largest triangle with the previous selected point and the next bucket's average
3. Result: `maxPoints` points that preserve the visual shape

## Canvas Layout

```
┌─────────────────────────────────────┐
│   ┌─────────────────────────────┐   │  --margin (20px)
│   │                             │   │
│   │    Loss Curve (canvas)      │   │
│   │                             │   │
│   │   ╱╲        ╱╲              │   │
│   │  ╱  ╲  ╱╲  ╱  ╲            │   │
│   │ ╱    ╲╱  ╲╱    ╲           │   │
│   │╱                      ╲    │   │
│   └─────────────────────────────┘   │
│   step 0                    step N  │
└─────────────────────────────────────┘
```

## Acceptance

- [ ] One `LossChart` class used for both live and replay modes (different `mode` option)
- [ ] Append-only: `appendPoint()` adds to end, never modifies existing points
- [ ] Throttle: at 50ms interval, no full re-render per SSE tick
- [ ] Downsample: 2000 max points, LTTB preserves curve shape at 10,000 steps
- [ ] Replay: `setData()` renders all points immediately without animation
- [ ] Resize: `resize()` recalculates dimensions on container/window resize
- [ ] Cleanup: `destroy()` cancels pending animation frames