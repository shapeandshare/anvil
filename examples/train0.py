"""train0: Bigram count table — no neural net, no gradients."""
import random
random.seed(42)

docs = [l.strip() for l in open("input.txt") if l.strip()]
uchars = sorted(set("".join(docs)))
BOS = len(uchars)
counts = {}
for doc in docs:
    tokens = [BOS] + [uchars.index(ch) for ch in doc] + [BOS]
    for i in range(len(tokens) - 1):
        key = (tokens[i], tokens[i + 1])
        counts[key] = counts.get(key, 0) + 1

total = sum(counts.values())
print(f"Stage 0: Bigram model — {total} transitions")