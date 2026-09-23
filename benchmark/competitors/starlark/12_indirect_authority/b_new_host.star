# Sends a receipt through a mail library; the program names no host itself.
load("mailer.star", "send")

to = read_line().strip()
print(send(to, "Your receipt: 2 items, 450"))
