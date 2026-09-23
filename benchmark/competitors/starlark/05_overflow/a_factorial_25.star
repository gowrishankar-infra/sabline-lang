# 25! does not fit in 64 bits; the loop passes that point at 21!.


def factorial(n):
    f = 1
    for i in range(1, n + 1):
        f = f * i  # DANGER
    return f


print(factorial(25))
