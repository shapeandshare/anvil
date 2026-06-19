import math


class Value:
    __slots__ = ("_children", "_local_grads", "data", "grad")

    def __init__(self, data, children=(), local_grads=()):
        self.data = data
        self.grad = 0
        self._children = children
        self._local_grads = local_grads

    def __add__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data + other.data, (self, other), (1, 1))

    def __mul__(self, other):
        other = other if isinstance(other, Value) else Value(other)
        return Value(self.data * other.data, (self, other), (other.data, self.data))

    def __pow__(self, other):
        return Value(self.data**other, (self,), (other * self.data ** (other - 1),))

    def log(self):
        return Value(math.log(self.data), (self,), (1 / self.data,))

    def exp(self):
        return Value(math.exp(self.data), (self,), (math.exp(self.data),))

    def relu(self):
        return Value(max(0, self.data), (self,), (float(self.data > 0),))

    def silu(self):
        """SiLU (Swish): f(x) = x * sigmoid(x)"""
        s = 1 / (1 + math.exp(-self.data))
        return Value(
            self.data * s,
            (self,),
            (s + self.data * s * (1 - s),),
        )

    def __neg__(self):
        return self * -1

    def __radd__(self, other):
        return self + other

    def __sub__(self, other):
        return self + (-other)

    def __rsub__(self, other):
        return other + (-self)

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        return self * other**-1

    def __rtruediv__(self, other):
        return other * self**-1

    def backward(self):
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
