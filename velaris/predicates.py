"""The in-toto predicate types Velaris writes, and the ones it reads as the
same types.
"""
from .version import SITE

# ---------------------------------------------------------------------------
# PREDICATE TYPES
#
#     A predicate type is a name, and a name on a domain means what whoever
#     holds that domain says it means. From 8.3 the two types this producer
#     writes name velaris-lang.dev, which this project holds. Before 8.3 they
#     named the project's GitHub Pages address - capability/v1 from 4.2,
#     receipt/v1 from 8.1 - and every Statement signed until then names that
#     address, which now redirects to velaris-lang.dev. A reader of Statements
#     (velaris verify, receipts diff, replay) takes both spellings as the same
#     type, and no other. velaris.dev was never this project's: 4.1 chose not
#     to use it, it is registered to someone else, and a Statement naming a
#     type under it is refused like any other type Velaris does not define.
# ---------------------------------------------------------------------------

CAPABILITY_PREDICATE_TYPE = SITE + "/capability/v1"
RECEIPT_PREDICATE_TYPE = SITE + "/receipt/v1"

# where both types were named until 8.3
EARLIER_SITE = "https://gowrishankar-infra.github.io/velaris-lang"

# what a reader accepts for each type: the name written now, first
CAPABILITY_PREDICATE_TYPES = (CAPABILITY_PREDICATE_TYPE,
                              EARLIER_SITE + "/capability/v1")
RECEIPT_PREDICATE_TYPES = (RECEIPT_PREDICATE_TYPE,
                           EARLIER_SITE + "/receipt/v1")


def predicate_kind(predicate_type: object) -> str | None:
    """'capability' or 'receipt' for a predicate type this Velaris reads,
    None for any other."""
    if isinstance(predicate_type, str):
        if predicate_type in CAPABILITY_PREDICATE_TYPES:
            return "capability"
        if predicate_type in RECEIPT_PREDICATE_TYPES:
            return "receipt"
    return None
