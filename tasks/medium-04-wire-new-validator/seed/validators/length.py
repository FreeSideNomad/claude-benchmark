def validate_length(value):
    if len(value) > 20:
        return "too_long"
    return None
