"""Pages blueprint package — all page-rendering (HTML) routes."""

from flask import Blueprint

pages_bp = Blueprint("pages", __name__)

# Import sub-modules to register routes on pages_bp
from user_app.blueprints.pages import core, rfpo, team, ticket  # noqa: E402, F401
