# The control: 25! exactly. The answer needs 84 bits, and it is the right answer.
product = 1
for i in range(1, 26):
    product = product * i
print(product)
