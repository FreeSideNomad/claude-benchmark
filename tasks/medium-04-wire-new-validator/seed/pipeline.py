from validators.length import validate_length

_VALIDATORS = [validate_length]


def validate(value):
    errors = []
    for validator in _VALIDATORS:
        error = validator(value)
        if error:
            errors.append(error)
    return errors
