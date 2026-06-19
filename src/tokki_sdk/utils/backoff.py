def fibonacci_backoff(attempt: int, delay: float = 0.5) -> float:
    if attempt <= 0:
        return delay
    elif attempt == 1:
        return delay
    else:
        a, b = 0, 1
        for _ in range(2, attempt + 1):
            a, b = b, a + b
        return b * delay
