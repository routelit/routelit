import asyncio
from typing import AsyncGenerator, Generator, TypeVar

# A generic type variable for the items being yielded
T = TypeVar("T")


def async_to_sync_generator(async_gen: AsyncGenerator[T, None]) -> Generator[T, None, None]:
    """
    Converts an asynchronous generator into a synchronous generator.

    This function runs an event loop to run the async generator and yields its
    results in a synchronous manner. It properly handles cleanup when the
    sync generator is closed early.

    Args:
        async_gen: The asynchronous generator to convert.

    Yields:
        The items from the asynchronous generator.
    """
    loop = None
    async_iterator = None
    loop_was_created = False

    try:
        # Get or create an event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop_was_created = True

        # Get the asynchronous iterator from the async generator
        async_iterator = async_gen.__aiter__()

        while True:
            try:
                # Run the __anext__() coroutine to get the next item.
                # loop.run_until_complete() blocks until the coroutine is done.
                item = loop.run_until_complete(async_iterator.__anext__())
                yield item
            except StopAsyncIteration:
                # The async generator is exhausted, so we break the loop.
                break
            except GeneratorExit:
                # The sync generator was closed, clean up the async generator
                print("Sync generator closed, cleaning up async generator")
                try:
                    if async_iterator is not None:
                        # Close the async generator
                        close_coro = async_iterator.aclose()  # type: ignore[attr-defined]
                        loop.run_until_complete(close_coro)
                except Exception as e:
                    print(f"Error during async generator cleanup: {e}")
                raise
    except Exception as e:
        # Handle any other exceptions during cleanup
        if async_iterator is not None:
            try:
                print(f"Exception occurred, cleaning up async generator: {e}")
                close_coro = async_iterator.aclose()  # type: ignore[attr-defined]
                if loop is not None:
                    loop.run_until_complete(close_coro)
            except Exception as cleanup_error:
                print(f"Error during exception cleanup: {cleanup_error}")
        raise
    finally:
        # Clean up the event loop if we created it
        if loop_was_created and loop is not None:
            try:
                loop.close()
            except Exception as e:
                print(f"Error closing event loop: {e}")
