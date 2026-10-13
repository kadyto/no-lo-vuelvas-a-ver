import unicodedata


def normalize(value):
    return " ".join(
        "".join(c for c in unicodedata.normalize("NFKD", value or "") if not unicodedata.combining(c))
        .casefold()
        .split()
    )
