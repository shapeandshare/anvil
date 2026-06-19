"""FastAPI web server and presentation layer.

``anvil.api`` contains the FastAPI application, route definitions
(under ``v1/``), Jinja2 HTML templates, and static assets (CSS
tokens, components, archetypes, JavaScript). Routes delegate to the
``AnvilWorkbench`` god class for all business logic.
"""
