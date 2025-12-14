from fastapi import FastAPI

app = FastAPI(title="Vekolom API")

@app.get("/health")
def health():
    return {"status": "ok"}