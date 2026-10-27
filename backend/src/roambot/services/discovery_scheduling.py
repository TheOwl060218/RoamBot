"""Show a useful first batch without adding model rounds or dropping the tail."""


def initial_batch_size(count):
    if count <= 4:
        return count
    # The original schedule was 4, 6, 6, ... . Keep its maximum number of
    # batches, but move work after the first visible result where possible.
    later_batches = (count - 4 + 5) // 6
    return max(2, count - later_batches * 6)


def assessment_batch_size(count, *, first=False):
    # Direct assessment produces observations and final copy in one response.
    # Bound the per-call output rather than raising the timeout for a six-card tail.
    return min(count, 2 if first else 3)
