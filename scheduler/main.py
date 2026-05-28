from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def hello(request: Request) -> dict[str, str | None]:
    # Kong injects these after successful auth.
    return {
        "message": "hello from FastAPI",
        "consumer": request.headers.get("x-consumer-username"),
        "credential": request.headers.get("x-credential-identifier"),
    }