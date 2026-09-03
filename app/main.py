from fastapi import FastAPI

app = FastAPI(title="Usage Metering and Billing Engine")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
