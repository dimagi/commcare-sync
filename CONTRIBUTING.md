# Contributing to CommCare Data Pipeline

## Coding style

> Perfection is achieved, not when there is nothing more to add, but
> when there is nothing left to take away.
>
> -- Antoine de Saint-Exupéry

### Avoid using comments, docstrings, and type hints.

In Python, comments, docstrings, and type hints, are all forms of
source code documentation. We believe that documentation should explain
the code only when the code is not self-explanatory.

Don't use comments to indicate _what_ the code does; that should be
obvious from the code itself. Use comments to explain _why_ the code
does what it does, and only when it might not be clear.

Avoid docstrings on methods or functions where their purpose is clear
from the name. Use docstrings to give the purpose of a module or class,
if necessary.

Use reStructuredText format in docstrings.

Only use type hints when:

* it would be useful to know a parameter's class,
* or a parameter's name is ambiguous or does not uniquely indicate its type,
* or a return value is not obvious from the name of the function or method.

If you do use a type hint in a function or method definition, then
include type hints for all its parameters and its return value, for the
sake of readability.

Use type aliases where it would clarify the type or purpose of a
variable, e.g. `type CredentialsType = tuple[UsernameType, PasswordType]`.

### Tests

Tests can be an excellent reference for the behavior of a codebase when
they are simple, and readable, and comprehensive. Tests must meet those
criteria.

If it is difficult to write tests that are simple, and readable, and
comprehensive, often that is because the code to be tested needs to be
refactored. Refactor it, for the benefit of the code, and the tests.

Don't use docstrings for test functions. The function's name should
explain what it is testing — If it doesn't, rename it.

#### Pythonic pytest

Take advantage of pytest features where possible. e.g. Combine
repetitive tests using pytest parametrized tests.

Use [pytest-unmagic](https://github.com/dimagi/pytest-unmagic) to make
pytest fixtures explicit.

Use Pythonic assert statements.

#### Doctests

Use doctests to demonstrate usage or behavior in a simple way. Run
doctests from an appropriate test module. For example,

```python
# some/tests/module.py
import doctest
import some.module as module

def test_doctests():
    results = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
```

## Commits

Each commit should do exactly one thing so that its diff is easy to
review. If a task involves multiple changes, split them into separate
commits. For example, whenever code is moved and changed, or a file is
renamed and changed, do the move or the rename in one commit and make
the changes in another.
