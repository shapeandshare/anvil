# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Reverse-mode autograd engine over scalar computation graphs.

Provides the ``Value`` class, a scalar wrapper that records operations
and supports reverse-mode differentiation via topological backpropagation.
"""

import math


class Value:
    """A scalar node in a reverse-mode autograd computation graph.

    Stores ``data``, ``grad``, ``_children`` (dependency nodes), and
    ``_local_grads`` (local derivatives). Operators build the graph;
    ``backward()`` propagates gradients via chain rule.
    """

    __slots__ = ("_children", "_local_grads", "data", "grad")

    def __init__(self, data, children=(), local_grads=()):
        self.data = data
        self.grad = 0
        self._children = children
        self._local_grads = local_grads

    def __add__(self, other):
        """Return the elementwise sum as a new ``Value``."""
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data + other.data, (self, other), (1, 1))

    def __mul__(self, other):
        """Return the elementwise product as a new ``Value``."""
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data * other.data, (self, other), (other.data, self.data))

    def __pow__(self, other):
        """Return ``self`` raised to a scalar power as a new ``Value``."""
        return Value(self.data**other, (self,), (other * self.data ** (other - 1),))

    def log(self):
        """Return the natural logarithm as a new ``Value``."""
        return Value(math.log(self.data), (self,), (1 / self.data,))

    def exp(self):
        """Return ``e`` raised to ``self.data`` as a new ``Value``."""
        return Value(math.exp(self.data), (self,), (math.exp(self.data),))

    def relu(self):
        """Return the ReLU activation: ``max(0, data)`` as a new ``Value``."""
        return Value(max(0, self.data), (self,), (float(self.data > 0),))

    def silu(self):
        """SiLU (Swish): f(x) = x * sigmoid(x)."""
        s = 1 / (1 + math.exp(-self.data))
        return Value(
            self.data * s,
            (self,),
            (s + self.data * s * (1 - s),),
        )

    def __neg__(self):
        """Return the negated value as a new ``Value``."""
        return self * -1

    def __radd__(self, other):
        """Return ``other + self`` (reflected addition)."""
        return self + other

    def __sub__(self, other):
        """Return the elementwise difference as a new ``Value``."""
        return self + (-other)

    def __rsub__(self, other):
        """Return ``other - self`` (reflected subtraction)."""
        return other + (-self)

    def __rmul__(self, other):
        """Return ``other * self`` (reflected multiplication)."""
        return self * other

    def __truediv__(self, other):
        """Return the elementwise quotient as a new ``Value``."""
        return self * other**-1

    def __rtruediv__(self, other):
        """Return ``other / self`` (reflected division)."""
        return other * self**-1

    def backward(self):
        """Compute gradients via reverse-mode autograd.

        Performs an iterative topological sort of the computation graph
        rooted at this node, then backpropagates by applying the chain
        rule along each edge.
        """
        topo = []
        visited = set()

        # Iterative topological sort to avoid RecursionError on deep graphs
        stack = [(self, False)]
        while stack:
            v, processed = stack.pop()
            if processed:
                topo.append(v)
            elif v not in visited:
                visited.add(v)
                stack.append((v, True))
                for child in v._children:
                    if child not in visited:
                        stack.append((child, False))
        self.grad = 1
        for v in reversed(topo):
            for child, local_grad in zip(v._children, v._local_grads, strict=True):
                child.grad += local_grad * v.grad
