# Multiplies a balance held in a record field by a rate from input; the product leaves 64 bits.
import sys
from dataclasses import dataclass


@dataclass
class Account:
    owner: str
    balance: int


def apply_rate(acc: Account, rate: int) -> Account:
    return Account(acc.owner, acc.balance * rate)  # DANGER


line = sys.stdin.readline().strip()
acc = Account("g", 1234567890123456)
try:
    rate = int(line)
except ValueError:
    print("not a number: " + line)
else:
    print(apply_rate(acc, rate).balance)
