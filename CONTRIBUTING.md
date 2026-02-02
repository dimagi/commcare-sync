# Contributing to CommCare Data Pipeline

## Coding style

> Perfection is achieved, not when there is nothing more to add, but
> when there is nothing left to take away.
>
> -- Antoine de Saint-Exupéry

### Avoid using comments, docstrings, and type hints.

Don't use comments to indicate _what_ the code does; that should be
obvious from the code itself. Use comments to explain _why_ the code
does what it does, and only when it might not be clear.

Use docstrings to give the purpose of a module or class. Avoid
docstrings on methods or functions where their purpose is clear from the
name. Use reStructuredText format in docstrings.

Only use type hints when:

* it would be useful to know a parameter's class,
* or where a parameter's type is not obvious from its name,
* or a function's or method's return value is not obvious from the
  function's or method's name.

If you do use a type hint in a function or method definition, then
include type hints for all its parameters and its return value, for the
sake of readability. Use type aliases (e.g.
`type CredentialsType = tuple[UsernameType, PasswordType]`) where it
would clarify the type or purpose of a variable.

### Tests

#### Pythonic pytest

Don't use docstrings for test functions. The function's name should
explain what it is testing.

Take advantage of pytest features where possible. e.g. Combine
repetitive tests using pytest parametrized tests.

Use [pytest-unmagic](https://github.com/dimagi/pytest-unmagic) to make
pytest fixtures explicit.

Use Pythonic assert statements.

#### Doctests

Add doctests for functions and methods where a doctest can demonstrate
usage in a simple way. Doctests can augment but should not replace unit
tests. Run doctests from an appropriate test module. For example,

```python
# tests/some/module.py
import some.module as module

def test_doctests():
    results = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
```
