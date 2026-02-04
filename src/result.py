from functools import wraps
import inspect
import logging
import traceback
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


@overload
def safe_fn(func: Callable[P, Coroutine[Any, Any, Result[T, E]]]) -> Callable[P, Coroutine[Any, Any, Result[T, E]]]: ...

@overload
def safe_fn(func: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, Coroutine[Any, Any, Result[T, Exception]]]: ...

@overload
def safe_fn(func: Callable[P, Result[T, E]]) -> Callable[P, Result[T, E]]: ...

@overload
def safe_fn(func: Callable[P, T]) -> Callable[P, Result[T, Exception]]: ...

def safe_fn(func):
    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                res = await func(*args, **kwargs)
                return res if isinstance(res, Result) else Ok(res)
            except BaseException as e:
                return Err(e)
        return async_wrapper

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            res = func(*args, **kwargs)
            # if func already returns a Result, propagate it directly
            return res if isinstance(res, Result) else Ok(res)
        except BaseException as e:
            return Err(e)
    return wrapper


@overload
def safe_call(fn: Callable[P, Coroutine[Any, Any, T]], *args: P.args, log_exception: bool = True, **kwargs: P.kwargs) -> Coroutine[Any, Any, tuple[T | None, Exception | None]]: ...

@overload
def safe_call(fn: Callable[P, T], *args: P.args, log_exception: bool = True, **kwargs: P.kwargs) -> tuple[T | None, Exception | None]: ...

def safe_call(fn, *args, log_exception=True, **kwargs):
    if inspect.iscoroutinefunction(fn):
        async def async_wrapper():
            try:
                return await fn(*args, **kwargs), None
            except Exception as e:
                tb = traceback.format_exc()
                if log_exception:
                    logging.error("Exception in %s:\n%s", fn.__name__, tb)
                return None, e
        return async_wrapper()

    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        tb = traceback.format_exc()
        if log_exception:
            logging.error("Exception in %s:\n%s", fn.__name__, tb)
        return None, e
