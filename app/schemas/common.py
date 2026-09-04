def normalize_label(value: str) -> str:
    return " ".join(value.casefold().split())
