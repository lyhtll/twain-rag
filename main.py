from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import ask

app = FastAPI(title="Mark Twain QA")
app.include_router(ask.router)
# Mounted last so /ask keeps priority; html=True serves static/index.html at /.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
