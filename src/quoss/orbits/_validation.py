"""Input validators shared by the orbit modules.

Private to :mod:`quoss.orbits`. Every public entry point in ``frames.py``,
``kepler.py`` and ``perturbations.py`` funnels its arguments through these,
because a physics function that trusts its inputs relocates the error to
wherever the ``nan`` eventually surfaces — which is never where it was made.

The two validators lived in ``frames.py`` and ``kepler.py`` as byte-identical
copies until ``perturbations.py`` needed them a third time. They enforce the
array contract of :mod:`quoss.core.types`, so there is exactly one place where
that contract is spelled out.

Broadcasting is *not* here. ``frames._broadcast_against`` and
``kepler._broadcast_to_common`` differ in shape and in what their messages
advise, and collapsing them would produce a helper that says less than either.

Freezing is not here either, and for a harder reason: the containers that need it
include :class:`~quoss.core.types.TimeGrid`, which lives in ``core`` and may not
import from ``orbits``. :func:`~quoss.core.types.frozen_copy` and
:func:`~quoss.core.types.frozen_view` therefore sit beside the array aliases they
enforce, which is the lowest layer that needs them.
"""

from __future__ import annotations

import numpy as np

from quoss.core.errors import DomainError
from quoss.core.types import FloatArray, FloatLike, Vec3Array

__all__ = ["as_1d", "as_vec3"]


def as_1d(name: str, value: FloatLike) -> FloatArray:
    """Return ``value`` as a finite 1-D ``float64`` array.

    Parameters
    ----------
    name : str
        Argument name, used in the error message.
    value : float or FloatArray
        Value to validate. A scalar becomes a length-1 array.

    Returns
    -------
    FloatArray
        The validated array.

    Raises
    ------
    DomainError
        If the value has more than one dimension, is empty, or is not finite.
    """
    arr = np.atleast_1d(np.asarray(value, dtype=np.float64))
    if arr.ndim != 1:
        raise DomainError(f"{name} must be scalar or 1-D, got shape {arr.shape}.")
    if arr.size == 0:
        raise DomainError(f"{name} must contain at least one value.")
    if not np.all(np.isfinite(arr)):
        raise DomainError(f"{name} contains non-finite values.")
    return arr


def as_vec3(name: str, value: Vec3Array) -> Vec3Array:
    """Return ``value`` as a finite ``(n, 3)`` ``float64`` array.

    Parameters
    ----------
    name : str
        Argument name, used in the error message.
    value : Vec3Array
        Stack of 3-vectors, time along the leading axis. A single ``(3,)``
        vector is accepted and promoted to ``(1, 3)``.

    Returns
    -------
    Vec3Array
        The validated array.

    Raises
    ------
    DomainError
        If the trailing axis is not of length 3, the array is not 2-D, it is
        empty, or it is not finite.
    """
    arr = np.asarray(value, dtype=np.float64)
    if arr.ndim == 1 and arr.shape[0] == 3:
        arr = arr[np.newaxis, :]
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise DomainError(
            f"{name} must have shape (n, 3) with time on the leading axis, "
            f"got {arr.shape}. Vec3Array puts the vector components last."
        )
    if arr.shape[0] == 0:
        raise DomainError(f"{name} must contain at least one vector.")
    if not np.all(np.isfinite(arr)):
        raise DomainError(f"{name} contains non-finite values.")
    return arr
