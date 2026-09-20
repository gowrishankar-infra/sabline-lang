"""The in-toto predicate types Sabline writes, and the ones it reads as the
same types.
"""
from .version import SITE

# ---------------------------------------------------------------------------
# PREDICATE TYPES
#
#     A predicate type is a name, and a name on a domain means what whoever
#     holds that domain says it means. From 8.6 the two types this producer
#     writes name sabline.dev, which this project holds. They have been
#     named twice before, and every Statement signed under either name is
#     still read as the same type:
#
#       4.2 to 8.2.1   the project's GitHub Pages address
#                      (capability/v1 from 4.2, receipt/v1 from 8.1)
#       8.3 to 8.5     velaris-lang.dev, the domain this project held
#                      before it was renamed Sabline (8.6)
#
#     Both addresses redirect to sabline.dev, and both pages are still
#     served there. A reader of Statements (sabline verify, receipts diff,
#     replay) takes all three spellings as the same type, and no other.
#
#     velaris.dev was never this project's: 4.1 chose not to use it, it is
#     registered to someone else, no release ever wrote a type under it,
#     and a Statement naming one is refused like any other type Sabline
#     does not define. Neither is velaris.io, the company whose name this
#     project moved away from.
# ---------------------------------------------------------------------------

CAPABILITY_PREDICATE_TYPE = SITE + "/capability/v1"
RECEIPT_PREDICATE_TYPE = SITE + "/receipt/v1"

# where both types were named before sabline.dev, newest first. Each is a
# name that was published and signed into Statements that still exist, so
# nothing is ever removed from this tuple - a name only ever joins it.
EARLIER_SITES = ("https://velaris-lang.dev",
                 "https://gowrishankar-infra.github.io/velaris-lang")

# the address the pages were served from before 8.3, kept under its own
# name because build_docs.py and the crosswalk still ask for it by that
EARLIER_SITE = EARLIER_SITES[-1]

# what a reader accepts for each type: the name written now, first
CAPABILITY_PREDICATE_TYPES = (
    (CAPABILITY_PREDICATE_TYPE,)
    + tuple(site + "/capability/v1" for site in EARLIER_SITES))
RECEIPT_PREDICATE_TYPES = (
    (RECEIPT_PREDICATE_TYPE,)
    + tuple(site + "/receipt/v1" for site in EARLIER_SITES))


def predicate_kind(predicate_type: object) -> str | None:
    """'capability' or 'receipt' for a predicate type this Sabline reads,
    None for any other."""
    if isinstance(predicate_type, str):
        if predicate_type in CAPABILITY_PREDICATE_TYPES:
            return "capability"
        if predicate_type in RECEIPT_PREDICATE_TYPES:
            return "receipt"
    return None
