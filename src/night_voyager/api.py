from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Night Voyager API", version="0.0.0")

    def health() -> dict[str, str]:
        return {"service": "night-voyager-api", "status": "ok"}

    app.add_api_route("/health", health, methods=["GET"])
    return app


app = create_app()
