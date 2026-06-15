## Summary

Commit-and-PR session: bundled 40 files of accumulated changes (design system polish, favicon/apple-touch-icon assets, template refinements, service updates, test updates, vault doc refreshes) into a single commit and opened PR #38 against main.

## Files changed

- `anvil/api/static/anvil-emblem.svg` — polished emblem SVG
- `anvil/api/static/apple-touch-icon.png` — new PWA touch icon
- `anvil/api/static/favicon.svg` — new favicon
- `anvil/api/static/css/archetypes.css` — expanded CSS archetypes
- `anvil/api/static/js/core.js` — minor JS tweaks
- `anvil/api/templates/archetypes/*.html` — refined hero, training, learn-index, experiment, faq, base templates
- `anvil/api/v1/{router,experiments,training,eval}.py` — route/service integration updates
- `anvil/cli.py` — CLI touch-ups
- `anvil/core/{engine.py,torch_engine.py,__init__.py}` — engine minor fixes
- `anvil/services/{training,inference,export}.py` — service refinements
- `tests/*` — test updates matching service changes
- `docs/{testing-guide.md,vault/**}` — doc refreshes

## Key decisions

- No new architectural decisions. This was a bundling and delivery session for accumulated work.