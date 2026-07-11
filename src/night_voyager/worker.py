def main() -> None:
    """Keep the bootstrap worker process alive without performing domain work."""
    import time

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
