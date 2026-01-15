def format_size(size: int | float) -> str:
    if size < 1000:
        return f"{int(size)} B"

    if size < 1_000_000:
        kbs = size / 1000
        return f"{round(kbs, 2)} KB"

    mbs = size / 1_000_000
    return f"{round(mbs, 2)} MB"

def format_percentage(part: int | float, whole: int | float) -> str:
    if whole == 0:
        return "0%"
    percentage = (part / whole) * 100
    return f"{round(percentage, 2)}%"
