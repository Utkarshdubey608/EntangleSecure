"""Registry of navigation pages so views can link to each other (filled in app.py)."""

PAGES: dict = {}


def link(container, name: str, label: str, icon: str | None = None) -> None:
    page = PAGES.get(name)
    if page is not None:
        container.page_link(page, label=label, icon=icon, width="stretch")
