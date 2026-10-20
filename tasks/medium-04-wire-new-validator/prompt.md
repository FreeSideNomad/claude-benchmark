Add a new validator in `validators/numeric.py`: `validate_numeric(value)`
returns the string `'not_numeric'` if `value` is not a string of only
digits (use `str.isdigit()`), otherwise returns `None`. Wire it into the
pipeline by adding it to `pipeline.py`'s list of validators (after the
existing length check), so `pipeline.validate(value)` includes
`'not_numeric'` in its result when applicable, alongside the existing
`'too_long'` check.
