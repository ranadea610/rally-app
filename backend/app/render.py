"""Single-origin Render entry point; the normal API entry point stays unchanged."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .main import app as api

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/api', api)
app.mount('/', StaticFiles(directory=Path('/app/static'), html=True), name='frontend')
