from fastapi import FastAPI

app = FastAPI(title="FlyRank Image Relevance")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
