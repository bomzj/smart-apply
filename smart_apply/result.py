from functools import wraps
import inspect
from typing import Callable, ParamSpec, TypeVar, Generic, Iterator, overload, Coroutine, Any

P = ParamSpec('P')  # For preserving args/kwargs types
T = TypeVar('T')
E = TypeVar('E')


class Result(Generic[T, E]):
    """Base class for Result type."""

    __slots__ = ()

    def __bool__(self) -> bool:
        raise NotImplementedError

    def __call__(self) -> T | E:
        raise NotImplementedError

    @property
    def ok(self) -> T | None:
        raise NotImplementedError

    @property
    def err(self) -> E | None:
        raise NotImplementedError

    def __iter__(self) -> Iterator[T | E | None]:
        # yield two values for flexible unpacking
        yield self.ok
        yield self.err


class Ok(Result[T, E]):
    __slots__ = ("value",)
    __match_args__ = ("value",)  # support match statement

    def __init__(self, value: T):
        self.value = value

    def __bool__(self) -> bool:
        return True

    def __call__(self) -> T:
        return self.value

    @property
    def ok(self) -> T:
        return self.value

    @property
    def err(self) -> None:
        return None

    def __repr__(self) -> str:
        return f"Ok({self.value!r})"


class Err(Result[T, E]):
    __slots__ = ("error",)
    __match_args__ = ("error",)  # support match statement

    def __init__(self, error: E):
        self.error = error

    def __bool__(self) -> bool:
        return False

    def __call__(self) -> E:
        return self.error

    @property
    def ok(self) -> None:
        return None

    @property
    def err(self) -> E:
        return self.error

    def __repr__(self) -> str:
        return f"Err({self.error!r})"


# ==========================================
# safe_call
# ==========================================

@overload
def safe_call(fn: Callable[P, Coroutine[Any, Any, Result[T, E]]], *args: P.args, **kwargs: P.kwargs) -> Coroutine[Any, Any, Result[T, E]]: ...

@overload
def safe_call(fn: Callable[P, Coroutine[Any, Any, T]], *args: P.args, **kwargs: P.kwargs) -> Coroutine[Any, Any, Result[T, Exception]]: ...

@overload
def safe_call(fn: Callable[P, Result[T, E]], *args: P.args, **kwargs: P.kwargs) -> Coroutine[Any, Any, Result[T, E]]: ...

@overload
def safe_call(fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Coroutine[Any, Any, Result[T, Exception]]: ...

async def safe_call(fn, *args, **kwargs):
    """
    A robust wrapper that handles sync, async, and lambda-wrapped 
    coroutines consistently. Always needs to be awaited. Returns a Result.
    """
    try:
        # 1. Execute the function
        res = fn(*args, **kwargs)

        # 2. If the result is a coroutine, await it
        if inspect.isawaitable(res):
            res = await res
            
        # 3. Wrap in Result object if not already wrapped
        if isinstance(res, Result): 
            return res
            
        return Ok(res)

    except Exception as e:
        return Err(e)


# ==========================================
# safe_fn
# ==========================================

@overload
def safe_fn(func: Callable[P, Coroutine[Any, Any, Result[T, E]]]) -> Callable[P, Coroutine[Any, Any, Result[T, E]]]: ...

@overload
def safe_fn(func: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, Coroutine[Any, Any, Result[T, Exception]]]: ...

@overload
def safe_fn(func: Callable[P, Result[T, E]]) -> Callable[P, Coroutine[Any, Any, Result[T, E]]]: ...

@overload
def safe_fn(func: Callable[P, T]) -> Callable[P, Coroutine[Any, Any, Result[T, Exception]]]: ...

def safe_fn(func):
    """
    A robust decorator that handles sync, async, and coroutine-returning 
    lambdas. Note: All functions decorated with this become async.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Simply delegate execution to safe_call
        return await safe_call(func, *args, **kwargs)

    return wrapper