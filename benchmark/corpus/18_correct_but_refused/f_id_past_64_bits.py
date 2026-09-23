# Builds a record id for a signed 64-bit database column from a customer number on input; this customer's id needs 67 bits.
import sys


def record_id(customer: int, order: int) -> int:
    return customer * 1000000000000 + order  # DANGER


line = sys.stdin.readline().strip()
try:
    customer = int(line)
except ValueError:
    print("not a number: " + line)
else:
    print("id " + str(record_id(customer, 42)))
