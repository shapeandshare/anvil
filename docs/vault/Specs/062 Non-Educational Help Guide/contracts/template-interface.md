# Contract: Help Page Template

**Type**: Jinja2 Template | **Version**: 1.0

## Template

`archetypes/help.html`

Extends `base.html`. Loads `archetypes.css` via `extra_css` block.

## Template Context

```python
{
    "sections": list[HelpSection],  # Ordered help sections
}
```

## Template Structure

```html
{% extends "base.html" %}
{% block extra_css %}<link rel="stylesheet" href="/static/css/archetypes.css">{% endblock %}
{% block content %}

<!-- Index / Navigation area -->
<div class="section-card">
  <div class="section-card__header">
    <span class="section-card__icon">...</span>
    <h2 class="section-card__title">Help</h2>
  </div>
  <div class="section-card__content">
    <p class="page-intro">...</p>
    <nav class="help-index">
      {% for section in sections %}
      <a href="#{{ section.anchor_id }}" class="help-index-item">
        <span class="help-index-item-title">{{ section.title }}</span>
        <span class="help-index-item-desc">{{ section.description }}</span>
      </a>
      {% endfor %}
    </nav>
  </div>
</div>

<!-- Detailed sections -->
{% for section in sections %}
<div class="section-card" id="{{ section.anchor_id }}">
  <div class="section-card__header">
    <h2 class="section-card__title">{{ section.title }}</h2>
    <a href="/v1/help" class="btn btn-sm btn-secondary">Back to index</a>
  </div>
  <div class="section-card__content">
    {{ section.content | safe }}
    {% if section.related_lesson_keys %}
    <div class="help-related-lessons">
      <strong>Related lessons:</strong>
      {% for key in section.related_lesson_keys %}
        {# resolve lesson title/path from frontend data if needed #}
      {% endfor %}
    </div>
    {% endif %}
  </div>
</div>
{% endfor %}

{% endblock %}
```

## Design Rules

- All spacing/typography MUST use CSS custom properties from `tokens.css`
- The `page-intro` class (from `components.css`) MUST be used for the introductory text
- Help section cards reuse the `section-card` component pattern
- Anchor links in the index use a flat list style (no numbered circles like learn-index)
- Code references within content use `<code>` tags styled by `code.css`