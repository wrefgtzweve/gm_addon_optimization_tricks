def format_size(size: int | float) -> str:
    is_negative = size < 0
    size = abs(size)
    
    if size < 1000:
        result = f"{int(size)} B"
    elif size < 1_000_000:
        kbs = size / 1000
        result = f"{round(kbs, 2)} KB"
    else:
        mbs = size / 1_000_000
        result = f"{round(mbs, 2)} MB"
    
    return f"-{result}" if is_negative else result

def format_percentage(part: int | float, whole: int | float) -> str:
    if whole == 0:
        return "0%"
    percentage = (part / whole) * 100
    return f"{round(percentage, 2)}%"
