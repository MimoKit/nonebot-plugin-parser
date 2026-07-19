def fmt_duration(duration: float) -> str:
    """格式化媒体时长，超过 1 小时后显示为 h:mm:ss。"""
    total_seconds = max(int(duration), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def fmt_count(value: int | float) -> str:
    """格式化计数：≥1 亿用 x.x亿，≥1 万用 x.x万，否则原样。"""
    number = float(value)
    if number >= 100_000_000:
        text = f"{number / 100_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{text}亿"
    if number >= 10_000:
        text = f"{number / 10_000:.1f}".rstrip("0").rstrip(".")
        return f"{text}万"
    if isinstance(value, float) and not number.is_integer():
        return f"{number:.1f}".rstrip("0").rstrip(".")
    return str(int(number))
