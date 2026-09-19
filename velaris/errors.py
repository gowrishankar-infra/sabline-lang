"""VelarisError, and the table of every error code it can carry.
"""
import json

from .version import REFERENCE_URL


# ---------------------------------------------------------------------------
# Friendly + machine-readable errors
# ---------------------------------------------------------------------------

class VelarisError(Exception):
    def __init__(self, code: str, message: str, line: int,
                 fixes: list[str] | None = None, file: str | None = None) -> None:
        self.code, self.message, self.line = code, message, line
        self.fixes = fixes or []
        self.file = file
        super().__init__(message)

    def human(self, filename: str) -> str:
        out = [f"error[{self.code}] {self.message}",
               f"  --> {self.file or filename}, line {self.line}"]
        if self.fixes:
            out.append("  how to fix (pick one):")
            for i, f in enumerate(self.fixes, 1):
                out.append(f"    {i}. {f}")
        # every error teaches where to read more (8.0)
        out.append(f"  reference: {REFERENCE_URL}")
        return "\n".join(out)

    def machine(self, filename: str) -> str:
        return json.dumps({
            "code": self.code, "message": self.message,
            "file": self.file or filename, "line": self.line,
            "fixes": self.fixes, "reference": REFERENCE_URL,
        }, indent=2)


# The error table: every code the compiler, the runtime and the library
# can report, with one line saying what it means. It is the only list.
# The published errors page is built from it, `check --sarif` makes one
# rule of each entry, and check_library.py reads this file's syntax tree
# and fails if a code is raised anywhere that is not here, or is here
# and raised nowhere. A code with two meanings says both.
ERROR_TABLE = {
    "E000": "a character the lexer cannot read, or a run that stopped "
            "without a Velaris error to report",
    "E001": "the program's file cannot be found",
    "E002": "an unknown escape sequence in a text literal",
    "E100": "the parser expected something else here",
    "E101": "a token that cannot start an expression here",
    "E102": "an expression that nests, or chains operators, too deeply, "
            "or blocks nested too deeply",
    "E200": "an unknown function, or an import with no such function",
    "E204": "a function named like a built-in, which would shadow it",
    "E300": "an effect used but not declared in 'uses', or a name in "
            "'uses' that is not an effect",
    "E310": "an effect outside the run's budget (while running); or a "
            "promise that calls a function with effects or uses 'try'",
    "E311": "a Python module outside the run's ffi: grants was reached",
    "E313": "a path outside the run's fs grants",
    "E314": "a host or port outside the run's net grants",
    "E315": "the run's fs or net operation count was reached",
    "E316": "a file larger than the read ceiling (raise it with --max-read)",
    "E317": "a network request whose socket peer is a proxy the run's net "
            "grants do not cover (an ambient HTTP_PROXY / HTTPS_PROXY)",
    "E318": "read_file on a documented credential location; read a secret "
            "with read_file_secret, or grant its exact path",
    "E400": "there is no 'main' function",
    "E401": "the wrong number of arguments, or parameters on 'main'",
    "E402": "an unknown variable, or break or continue, which the language "
            "does not have",
    "E403": "division or remainder by zero while running",
    "E405": "random(n) with n less than 1",
    "E406": "the placeholders in a format text and the values given do "
            "not match",
    "E407": "a whole number grew past 64 bits",
    "E408": "an exit code outside 0 to 255",
    "E500": "an unknown type",
    "E501": "types do not match",
    "E502": "a value is needed from a function that returns nothing",
    "E503": "a return does not match the declared return type",
    "E504": "an 'if' or 'while' condition that is not a Bool",
    "E505": "a requires, ensures or invariant that is not a Bool",
    "E506": "an empty list or map with no type to say what it holds",
    "E507": "a record defined twice, a field given twice in a record, or "
            "one name used for a record and a function",
    "E508": "an unknown record",
    "E509": "a record value with a missing, unknown or repeated field, "
            "or a map with a repeated key",
    "E510": "a field that the value does not have",
    "E511": "a record changed in place",
    "E512": "an imported file cannot be found",
    "E513": "a function or record defined in two files",
    "E514": "a variable named like an import",
    "E515": "an import from outside the directory a program is served "
            "from, or of a file there that is not a .vel file",
    "E520": "a failure that is ignored: a call that can fail, not "
            "handled with check or passed up with try",
    "E521": "'try' in a function that cannot fail, or a failure that "
            "escaped the program while running",
    "E522": "'try' or 'check' on a call that cannot fail",
    "E523": "'fail' in a function that does not declare 'or fail'",
    "E524": "'main' declared 'or fail'",
    "E525": "a check's ok arm names the result of a call that returns "
            "nothing, or leaves a returned value unnamed",
    "E530": "a function passed as a value that has effects or can fail",
    "E560": "a Secret given to something that emits it: a builtin with "
            "an effect, a generic function with an effect, or a 'fail' "
            "reason",
    "E561": "declassify without a reason written as text in the call, or "
            "given something that is not a Secret",
    "E562": "a Secret of a Secret",
    "E563": "an 'if' or 'while' branching on a value derived from a "
            "Secret",
    "E540": "a type variable that appears only in the return type",
    "E541": "a type variable named like a real type",
    "E542": "an argument that does not fit the shape a generic "
            "function's type variables took",
    "E543": "a generic function passed as a value",
    "E550": "amounts in two different currencies added, compared, or one "
            "given where the other is needed",
    "E551": "a currency that is not in velaris.CURRENCIES, or one not "
            "written as text in the call",
    "E552": "a rounding mode other than \"half_up\", \"half_even\" or "
            "\"down\", or one not written as text in the call",
    "E553": "an amount divided with '/' or '%', which would round "
            "without saying how",
    "E600": "a 'requires' broke while running",
    "E601": "an 'ensures' broke while running",
    "E602": "a position outside a list or text while running",
    "E607": "a text grew too large to build, or there was no input to "
            "read",
    "E608": "a file could not be written",
    "E609": "recursion too deep, a value nested too deeply, or split "
            "by empty text",
    "E610": "the run's time limit was reached and the program stopped",
    "E611": "the run's memory cap was reached and the program stopped",
    "E612": "a loop whose end cannot be shown (check --strict only)",
    "E613": "a check or audit ran past its time ceiling and was stopped",
    "E614": "a check or audit grew past its memory ceiling and was stopped",
    "E615": "a run under velaris eval was asked to stop from outside, and "
            "stopped at the next call or loop turn",
    "E616": "a run replayed with recorded tool responses made a call the "
            "recording does not hold, in that place",
    "E700": "a promise that is provably false, with the input that "
            "breaks it",
    "E701": "a call that can break the called function's 'requires', "
            "with the input that does",
    "E703": "a loop invariant the prover cannot show holds",
    "E704": "a loop invariant broke while running",
    "E705": "a list read the prover shows can go past the end",
    "E706": "a divisor the prover shows can be zero",
    "E999": "the self-test in 'velaris doctor' failed",
}

# Codes that were given once and are not given now, as (code, what it
# meant, the version that removed it). STABILITY.md rule 3: a code is
# never reused for a different meaning, and a removed one stays listed
# here and on the errors page. None has been removed since the rule was
# written (4.0); E610's reuse in 2.59 is in STABILITY.md's record.
REMOVED_ERRORS: tuple[tuple[str, str, str], ...] = ()


def _too_deep_error(running: bool) -> "VelarisError":
    """What a RecursionError is reported as (8.2): Python's own recursion
    limit, reached walking a program nested too deeply (E102) or a value a
    run built too deeply (E609). Until 8.2 either was a Python traceback
    (check_hostile.py)."""
    if running:
        return VelarisError("E609",
            "a value this program built is nested too deeply to print, "
            "compare or encode", 0,
            fixes=["build it flatter - a list of items rather than items "
                   "inside items",
                   "or keep less of it"])
    return VelarisError("E102",
        "this program nests too deeply to be read", 0,
        fixes=["move the innermost part into a function of its own",
               "split a long expression with 'let'"])
