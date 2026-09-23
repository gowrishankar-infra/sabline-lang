# Multiplies a balance held in a record field by a rate from input; the product leaves 64 bits.
# NOT-LIKE-FOR-LIKE: Starlark has no classes: the record is a dict.


def Account(owner, balance):
    return {"owner": owner, "balance": balance}


def apply_rate(acc, rate):
    return Account(acc["owner"], acc["balance"] * rate)  # DANGER


def main():
    line = read_line().strip()
    acc = Account("g", 1234567890123456)
    # Starlark has no try: check first what int() would refuse
    unsigned = line[1:] if line[:1] in ["+", "-"] else line
    if not unsigned.isdigit():
        print("not a number: " + line)
    else:
        rate = int(line)
        print(apply_rate(acc, rate)["balance"])


main()
