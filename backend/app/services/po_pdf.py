"""Purchase Order PDF: Jinja2 template -> HTML -> PDF (WeasyPrint)."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent.parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


def render_po_html(order: dict) -> str:
    return _env.get_template("po.html").render(order=order)


def render_po_pdf(order: dict) -> bytes:
    from weasyprint import HTML  # imported lazily: needs system libs

    return HTML(string=render_po_html(order)).write_pdf()
