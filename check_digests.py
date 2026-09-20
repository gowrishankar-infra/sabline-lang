#!/usr/bin/env python3
"""sha256, the encoders, and HMAC-SHA256 under a Secret key (8.5).

    python check_digests.py

The digests and encoders are held to published vectors. The two HMACs are
held to RFC 4231's, and then to the rule that makes them sound to have: the
key is a Secret of Text and nothing else, the MAC is the one thing that
comes out, the call needs the `declassify` effect and the grant, and the
audit and the receipt both say it happened - the receipt with the key's
fingerprint, never the key. The adversarial cases of 8.5's pass are here: a
key that tries to reach output by any route other than the MAC.
"""
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from suite_dirs import isolate  # noqa: E402

import sabline  # noqa: E402

WORK = isolate("check_digests")
FAILED: list[str] = []
PASSED = [0]
KEY = "a-key-only-this-suite-knows-4c1d"


def expect(what: str, ok: bool, detail: Any = "") -> None:
    if ok:
        PASSED[0] += 1
    else:
        FAILED.append(what)
        print(f"  FAILED: {what}" + (f"\n    {detail}" if detail != "" else ""))


def run(source: str, allow: str = "io,env,declassify",
        env: dict[str, str] | None = None) -> Any:
    saved = dict(os.environ)
    os.environ.update(env or {})
    try:
        return sabline.run(source, allow=allow)
    finally:
        os.environ.clear()
        os.environ.update(saved)


def codes(source: str) -> list[str]:
    return [p.code for p in sabline.check(source, prove=False).problems]


def main_of(body: str, uses: str = "io, env, declassify") -> str:
    return f"fn main() uses {uses} {{\n{body}\n}}\n"


def fallible(call: str) -> str:
    return (f"    check {call} {{\n        ok t {{ print(\"ok: \" + t) }}\n"
            f"        fail why {{ print(\"failed: \" + why) }}\n    }}")


def main() -> int:
    print("digests and encoders")
    got = run(main_of("\n".join([
        '    print(sha256(""))', '    print(sha256("abc"))',
        '    print(sha256("café"))',
        '    print(hex_encode("café"))',
        '    print(base64_encode("any carnal pleas"))',
        '    print(base64_encode(""))',
        '    print(url_encode("a b/c~d-e_f.g?h=i&j+k café"))',
        fallible('hex_decode("636166c3a9")'),
        fallible('base64_decode("Y2Fmw6k=")'),
        fallible('hex_decode("zz")'), fallible('hex_decode("abc")'),
        fallible('hex_decode("ff")'), fallible('hex_decode(" 6161")'),
        fallible('base64_decode("Y2Fm w6k=")'),
        fallible('base64_decode("!!!!")'),
        fallible('base64_decode("/w==")')])), "io")
    expect("sha256, hex, base64 and url_encode are the published values; a "
           "decoder fails on what is not the encoding, or not UTF-8",
           got.output.split("\n") == [
               "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
               "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
               "850f7dc43910ff890f8879c0ed26fe697c93a067ad93a7d50f466a7028a9bf4e",
               "636166c3a9", "YW55IGNhcm5hbCBwbGVhcw==", "",
               "a%20b%2Fc~d-e_f.g%3Fh%3Di%26j%2Bk%20caf%C3%A9",
               "ok: café", "ok: café",
               "failed: that text is not hexadecimal",
               "failed: that text is not hexadecimal",
               "failed: that hexadecimal does not decode to text (UTF-8)",
               "failed: that text is not hexadecimal",
               "failed: that text is not base64",
               "failed: that text is not base64",
               "failed: that base64 does not decode to text (UTF-8)", ""],
           (got.output, got.problems))
    expect("a decoder is fallible: ignoring it does not compile (E520)",
           codes(main_of('    print(hex_decode("61"))', "io")) == ["E520"])
    expect("a digest of a secret is a secret: printing one is E560",
           codes(main_of('    print(sha256(env("K", "")))', "io, env"))
           == ["E560"])
    expect("a decoder takes no secret: its failure would quote it (E560)",
           codes(main_of(fallible('base64_decode(env("K", ""))'), "io, env"))
           == ["E560"])
    mine = ("fn sha256(t: Text) -> Text {\n    return \"mine: \" + t\n}\n"
            + main_of('    print(sha256("x"))', "io"))
    got = run(mine, "io")
    expect("a program's own sha256 is still its own (SPEC.md 10.1)",
           got.output == "mine: x\n", (got.output, got.problems))

    print("hmac_sha256")
    got = run(main_of("\n".join([
        '    print(hmac_sha256(env("K1", ""), "what do ya want for nothing?"))',
        '    print(hmac_sha256(env("K2", ""), "The quick brown fox jumps over the lazy dog"))',
        '    print(hmac_sha256_chain(env("K2", ""), ["a", "b"]))'])),
        env={"K1": "Jefe", "K2": "key"})
    import hashlib
    import hmac
    chain = hmac.new(hmac.new(b"key", b"a", hashlib.sha256).digest(), b"b",
                     hashlib.sha256).hexdigest()
    expect("RFC 4231's test case 2, the well-known vector, and a chain that "
           "is HMAC under the raw bytes of the HMAC before it",
           got.output.split() == [
               "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843",
               "f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8",
               chain], (got.output, got.problems))
    sign = main_of('    print(hmac_sha256(env("K", ""), "m"))')
    expect("without `uses declassify` it does not compile (E300)",
           codes(main_of('    print(hmac_sha256(env("K", ""), "m"))',
                         "io, env")) == ["E300"])
    got = run(sign, "io,env", {"K": KEY})
    expect("without the declassify grant it does not run (E310)",
           [p.code for p in got.problems] == ["E310"]
           and got.refused_effect == "declassify", got.problems)
    expect("a key that is not a Secret is refused (E561)",
           codes(main_of('    print(hmac_sha256("plain", "m"))')) == ["E561"])
    expect("a message that carries a secret is refused (E560): its digest "
           "would leave",
           codes(main_of('    print(hmac_sha256(env("K", ""), env("M", "")))'))
           == ["E560"]
           and codes(main_of('    print(hmac_sha256_chain(env("K", ""), '
                             '[env("M", "")]))')) == ["E560"])
    expect("an empty chain is an error, not a digest of nothing (E609)",
           [p.code for p in run(main_of(
               "    let none: List of Text = []\n"
               '    print(hmac_sha256_chain(env("K", ""), none))'),
               env={"K": KEY}).problems] == ["E609"])
    secrets = sabline.audit(sign).secrets or {}
    expect("the audit lists the call under secrets, reason 'hmac signature'",
           secrets["declassifies"] is True
           and secrets["declassifications"] == [
               {"reason": "hmac signature", "function": "main", "line": 2,
                "builtin": "hmac_sha256"}], secrets)
    got = run(sign, env={"K": KEY})
    noted = got.receipt["predicate"]["declassifications"]
    expect("the receipt records it with the key's fingerprint - twelve hex "
           "digits - and the key is nowhere in it",
           len(noted) == 1 and noted[0]["reason"] == "hmac signature"
           and len(noted[0]["key_fingerprint"]) == 12
           and KEY not in json.dumps(got.receipt), noted)
    again = run(sign, env={"K": KEY})
    other = run(sign, env={"K": KEY + "x"})
    expect("the fingerprint is the same for the same key and differs for "
           "another",
           again.receipt["predicate"]["declassifications"][0]
           ["key_fingerprint"] == noted[0]["key_fingerprint"]
           != other.receipt["predicate"]["declassifications"][0]
           ["key_fingerprint"])

    print("a key that tries to leave by another route")
    routes = {
        "printed": '    print(env("K", ""))',
        "printed after a pure function": '    print(upper(env("K", "")))',
        "as the reason of a failure": '    exit_with(length(env("K", "")))',
        "written to a file": '    write_file("k.txt", env("K", ""))',
        "in a log line": '    log(env("K", ""))',
        "branched on": '    if env("K", "") == "a" {\n        print("a")\n    }',
        "as a tool's arguments": fallible('tool("t", env("K", ""))'),
        "as a URL": fallible('fetch("https://x.example/" + env("K", ""))'),
        "hex-encoded, then printed": '    print(hex_encode(env("K", "")))',
        "url-encoded into a request":
            fallible('fetch("https://x.example/?k=" + url_encode(env("K", "")))'),
        "through a list": '    print(get([env("K", "")], 0))',
        "through a map": '    print(get_or({"k": env("K", "")}, "k", env("K", "")))',
        "through format": '    print(format("{}", env("K", "")))',
        "through json_of": '    print(json_of([env("K", "")]))',
        "as the message of another MAC":
            '    print(hmac_sha256(env("J", ""), env("K", "")))',
    }
    for name, body in routes.items():
        found = codes(main_of(body, "io, env, fs, net, tool, declassify"))
        expect(f"the key {name}: does not compile",
               bool(found) and set(found) <= {"E560", "E563"}, found)
    loop = main_of(
        "    let key = env(\"K\", \"\")\n"
        "    let out = \"\"\n"
        "    for c in chars(key) {\n"
        "        out = out + c\n    }\n    print(out)")
    expect("the key walked a character at a time: still a secret (E560)",
           set(codes(loop)) <= {"E560", "E563"} and bool(codes(loop)),
           codes(loop))
    many = main_of(
        "    let key = env(\"K\", \"\")\n    let i = 0\n"
        "    while i < 40 {\n"
        "        let mac = hmac_sha256(key + to_text(i), \"m\")\n"
        "        i = i + 1\n    }\n    print(\"done\")")
    got = run(many, env={"K": KEY})
    prints = [d["key_fingerprint"] for d in
              got.receipt["predicate"]["declassifications"]]
    expect("a site that signs under many keys names sixteen of them and "
           "then says 'many': a receipt is not a place to write keys out",
           got.ok and len(prints) == 17 and prints.count("many") == 1
           and sum(d["times"] for d in
                   got.receipt["predicate"]["declassifications"]) == 40,
           (got.problems, prints))
    print("-" * 62)
    if FAILED:
        print(f"{len(FAILED)} FAILED, {PASSED[0]} passed")
        return 1
    print(f"all {PASSED[0]} checks passed: the MAC is the only thing an hmac "
          f"call lets out, and it says that it did")
    return 0


if __name__ == "__main__":
    sys.exit(main())
