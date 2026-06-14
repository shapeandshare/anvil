"""train2: Autograd replaces manual gradients."""
print("Stage 2: Autograd (Value class)")
from anvil.core.autograd import Value
a = Value(2.0)
b = Value(3.0)
c = a * b
L = c + a
L.backward()
print(f"a.grad = {a.grad:.1f} (expected 4.0)")
print(f"b.grad = {b.grad:.1f} (expected 2.0)")