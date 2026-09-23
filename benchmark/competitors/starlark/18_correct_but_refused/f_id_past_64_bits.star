# Builds a record id for a signed 64-bit database column from a customer number on input; this customer's id needs 67 bits.


def record_id(customer, order):
    return customer * 1000000000000 + order  # DANGER


def main():
    line = read_line().strip()
    # Starlark has no try: check first what int() would refuse
    unsigned = line[1:] if line[:1] in ["+", "-"] else line
    if not unsigned.isdigit():
        print("not a number: " + line)
    else:
        customer = int(line)
        print("id " + str(record_id(customer, 42)))


main()
