"""Velaris - the language where you can trust code you did not write.

The compiler, one module per stage, in the order a program goes
through them; _MODULES names them in that order. A module imports
only from the modules before it, but for the names its __forward__
lists, which this file binds once all are loaded. `import velaris`
gives every name velaris.py gave while it was one file (until 8.2),
and the run state (velaris/state.py) is read where it lives.
"""
import sys as _sys
import types as _types
import typing as _typing

_MODULES = (
    "version", "predicates", "errors", "lexer", "nodes", "parser",
    "tables", "confine", "state", "recorder", "loader", "values",
    "wrappers", "budget", "tools", "effects", "checker", "termination",
    "prover", "native", "runtime", "witnesses", "editor", "formatter",
    "project", "session", "results", "library", "pool",
    "findings", "mcp_manifest", "doors", "migrate", "ratchet",
    "conform", "attestation", "receipts", "statements", "receipt_diff",
    "evaluation", "replay",
    "upgrades", "stats",
    "eject", "permissions", "cli",
)

from . import version, predicates, errors, lexer, nodes, parser  # noqa: E402,F401
from . import tables, confine, state, recorder, loader, values  # noqa: E402,F401
from . import wrappers, budget, tools  # noqa: E402,F401
from . import effects, checker, termination, prover, native, runtime  # noqa: E402,F401
from . import witnesses  # noqa: E402,F401
from . import editor, formatter, project, session, results, library  # noqa: E402,F401
from . import pool, findings, mcp_manifest, doors, migrate, ratchet  # noqa: E402,F401
from . import conform, attestation, receipts, statements  # noqa: E402,F401
from . import receipt_diff, evaluation, replay  # noqa: E402,F401
from . import upgrades  # noqa: E402,F401
from . import stats, eject  # noqa: E402,F401
from . import permissions  # noqa: E402,F401
from . import cli  # noqa: E402,F401

from .version import (  # noqa: E402
    REFERENCE_URL as REFERENCE_URL,
    SITE as SITE,
    VERSION as VERSION,
)
from .predicates import (  # noqa: E402
    CAPABILITY_PREDICATE_TYPE as CAPABILITY_PREDICATE_TYPE,
    CAPABILITY_PREDICATE_TYPES as CAPABILITY_PREDICATE_TYPES,
    RECEIPT_PREDICATE_TYPE as RECEIPT_PREDICATE_TYPE,
    RECEIPT_PREDICATE_TYPES as RECEIPT_PREDICATE_TYPES,
    predicate_kind as predicate_kind,
)
from .errors import (  # noqa: E402
    ERROR_TABLE as ERROR_TABLE,
    REMOVED_ERRORS as REMOVED_ERRORS,
    VelarisError as VelarisError,
)
from .lexer import (  # noqa: E402
    ESCAPES as ESCAPES,
    KEYWORDS as KEYWORDS,
    MASTER_RE as MASTER_RE,
    TOKEN_SPEC as TOKEN_SPEC,
    Token as Token,
    fmt_fn_type as fmt_fn_type,
    fn_sig_parts as fn_sig_parts,
    lex as lex,
    type_mentions as type_mentions,
    unescape as unescape,
)
from .nodes import (  # noqa: E402
    Assign as Assign,
    BinOp as BinOp,
    Block as Block,
    Bool as Bool,
    Call as Call,
    Check as Check,
    Closure as Closure,
    ExprStmt as ExprStmt,
    FailStmt as FailStmt,
    FieldGet as FieldGet,
    FloatNum as FloatNum,
    Function as Function,
    If as If,
    Let as Let,
    ListLit as ListLit,
    MapLit as MapLit,
    Neg as Neg,
    Not as Not,
    Num as Num,
    RecordDef as RecordDef,
    RecordLit as RecordLit,
    Return as Return,
    Str as Str,
    TryExpr as TryExpr,
    Var as Var,
    While as While,
)
from .parser import (  # noqa: E402
    EXPR_CHAIN_LIMIT as EXPR_CHAIN_LIMIT,
    EXPR_NEST_LIMIT as EXPR_NEST_LIMIT,
    Parser as Parser,
    expr_str as expr_str,
    expr_vars as expr_vars,
    nice_name as nice_name,
)
from .tables import (  # noqa: E402
    ALLOW_ALL as ALLOW_ALL,
    ALL_EFFECTS as ALL_EFFECTS,
    BUILTINS as BUILTINS,
    CHECK_MEMORY_MB_DEFAULT as CHECK_MEMORY_MB_DEFAULT,
    CHECK_TIMEOUT_DEFAULT as CHECK_TIMEOUT_DEFAULT,
    CURRENCIES as CURRENCIES,
    DEFAULT_ALLOW as DEFAULT_ALLOW,
    FALLIBLE_BUILTINS as FALLIBLE_BUILTINS,
    HAVE_Z3 as HAVE_Z3,
    INT_MAX as INT_MAX,
    INT_MIN as INT_MIN,
    KNOWN_TYPES as KNOWN_TYPES,
    MONEY_BUILTINS as MONEY_BUILTINS,
    NEW_BUILTINS as NEW_BUILTINS,
    REDACTED as REDACTED,
    ROUNDING as ROUNDING,
    SECRET_BUILTINS as SECRET_BUILTINS,
    SECRET_SOURCES as SECRET_SOURCES,
    _z3_installed as _z3_installed,
    builtin_reached as builtin_reached,
    shown_name as shown_name,
)
from .recorder import (  # noqa: E402
    RECEIPT_SCHEMA as RECEIPT_SCHEMA,
    RECEIPT_SPEC as RECEIPT_SPEC,
    REFUSAL_CODES as REFUSAL_CODES,
    _RunRecorder as _RunRecorder,
    _entry_name as _entry_name,
    _note_error as _note_error,
    _note_redirect as _note_redirect,
    _note_stop as _note_stop,
    _refusal_effect as _refusal_effect,
    _utc_now_ms as _utc_now_ms,
)
from .loader import (  # noqa: E402
    _bind_new_builtins as _bind_new_builtins,
    _import_refusal as _import_refusal,
    _stdlib_dir as _stdlib_dir,
    blame as blame,
    load_program as load_program,
    qualify as qualify,
    unknown_function as unknown_function,
)
from .values import (  # noqa: E402
    FailSignal as FailSignal,
    HandleValue as HandleValue,
    MoneyValue as MoneyValue,
    OpaqueList as OpaqueList,
    RecElem as RecElem,
    RecListVal as RecListVal,
    RecordValue as RecordValue,
    ReturnSignal as ReturnSignal,
    _MONEY_TEXT as _MONEY_TEXT,
    money_text as money_text,
    parse_money_text as parse_money_text,
    round_ratio as round_ratio,
    to_text as to_text,
)
from .wrappers import (  # noqa: E402
    SECRET_PREFIX as SECRET_PREFIX,
    _outside_money as _outside_money,
    carries_secret as carries_secret,
    clash_error as clash_error,
    currency_clash as currency_clash,
    currency_generic as currency_generic,
    erase_wrappers as erase_wrappers,
    is_money as is_money,
    is_secret as is_secret,
    records_carrying as records_carrying,
    secret_inner as secret_inner,
    strip_secret as strip_secret,
    wrap_secret as wrap_secret,
)
from .budget import (  # noqa: E402
    Budget as Budget,
    BudgetError as BudgetError,
    _FFI_INERT as _FFI_INERT,
    _FFI_UNKNOWN as _FFI_UNKNOWN,
    _PCT_DECODE as _PCT_DECODE,
    _PCT_ENCODE as _PCT_ENCODE,
    _RedirectRefused as _RedirectRefused,
    _add_opener as _add_opener,
    _ascii_digits as _ascii_digits,
    _credential_root as _credential_root,
    _ffi_owner as _ffi_owner,
    _ffi_resolve as _ffi_resolve,
    _flag_value as _flag_value,
    _frozen_epoch as _frozen_epoch,
    _fs_grant_covers as _fs_grant_covers,
    _host_matches as _host_matches,
    _net_grant_covers as _net_grant_covers,
    _net_grant_text as _net_grant_text,
    _ordinal as _ordinal,
    _pct_decode as _pct_decode,
    _pct_encode as _pct_encode,
    _proxy_for as _proxy_for,
    allow_host as allow_host,
    allow_module as allow_module,
    allow_path as allow_path,
    checked_int as checked_int,
    cli_budget as cli_budget,
    count_op as count_op,
    expand_allow as expand_allow,
    ffi_reach as ffi_reach,
    guarded_opener as guarded_opener,
    host_refusal as host_refusal,
    parse_budget as parse_budget,
    parse_host_port as parse_host_port,
    run_params as run_params,
    set_run_params as set_run_params,
    spend as spend,
    trace_enter as trace_enter,
    trace_leave as trace_leave,
    warn_allow_all as warn_allow_all,
)
from .effects import (  # noqa: E402
    check_effects as check_effects,
    local_names_of as local_names_of,
)
from .checker import (  # noqa: E402
    check_main as check_main,
    check_types as check_types,
)
from .termination import (  # noqa: E402
    BAD as BAD,
    FLIP as FLIP,
    _conjuncts as _conjuncts,
    _limit_is_invariant as _limit_is_invariant,
    _names_bound_in as _names_bound_in,
    _steps_along_paths as _steps_along_paths,
    loop_termination as loop_termination,
)
from .prover import (  # noqa: E402
    FLOAT_PROOF_SECONDS as FLOAT_PROOF_SECONDS,
    PROOF_SECONDS as PROOF_SECONDS,
    PROOF_TIMEOUT_ENV as PROOF_TIMEOUT_ENV,
    PROVER_SEED_ENV as PROVER_SEED_ENV,
    _proof_seconds as _proof_seconds,
    _shown_name as _shown_name,
    check_proofs as check_proofs,
    proof_timeout_env as proof_timeout_env,
    proof_timeout_seconds as proof_timeout_seconds,
    prover_seed as prover_seed,
    set_proof_timeout as set_proof_timeout,
)
from .native import (  # noqa: E402
    _compile_native as _compile_native,
    compile_native as compile_native,
    native_eligible as native_eligible,
)
from .runtime import (  # noqa: E402
    BUILTIN_EFFECTS as BUILTIN_EFFECTS,
    _needs_big_stack as _needs_big_stack,
    _run_on_big_stack as _run_on_big_stack,
    build_runtime as build_runtime,
    interpret as interpret,
    run_builtin as run_builtin,
    run_money as run_money,
)
from .editor import (  # noqa: E402
    contract_coverage as contract_coverage,
    editor_answer as editor_answer,
    inspect_source as inspect_source,
    lsp_analyze as lsp_analyze,
    lsp_serve as lsp_serve,
)
from .formatter import (  # noqa: E402
    UNARY_BEFORE as UNARY_BEFORE,
    UNARY_KEYWORDS as UNARY_KEYWORDS,
    fmt_main as fmt_main,
    format_source as format_source,
)
from .project import (  # noqa: E402
    LOCKFILE as LOCKFILE,
    LOCK_SCHEMA as LOCK_SCHEMA,
    MANIFEST as MANIFEST,
    STARTER as STARTER,
    _digest_of as _digest_of,
    _lock_path as _lock_path,
    _lock_read as _lock_read,
    _lock_write as _lock_write,
    _manifest_read as _manifest_read,
    _manifest_write as _manifest_write,
    build_program as build_program,
    doctor as doctor,
    gather_sources as gather_sources,
    new_project as new_project,
    packages as packages,
    verify_libraries as verify_libraries,
)
from .session import (  # noqa: E402
    repl as repl,
)
from .results import (  # noqa: E402
    AUDIT_SCHEMA as AUDIT_SCHEMA,
    AuditResult as AuditResult,
    CheckResult as CheckResult,
    Problem as Problem,
    RunResult as RunResult,
    _as_problem as _as_problem,
    _problem_of as _problem_of,
)
from .library import (  # noqa: E402
    _FFI_CALLS as _FFI_CALLS,
    _NATIVE_SUFFIXES as _NATIVE_SUFFIXES,
    _OUT_OF_MEMORY_SIGNS as _OUT_OF_MEMORY_SIGNS,
    _WindowsMemoryJob as _WindowsMemoryJob,
    _audit_here as _audit_here,
    _budget_from as _budget_from,
    _cap_this_process as _cap_this_process,
    _ceiling_args as _ceiling_args,
    _check_here as _check_here,
    _ffi_modules_named as _ffi_modules_named,
    _ffi_named as _ffi_named,
    _ffi_native as _ffi_native,
    _fs_net_named as _fs_net_named,
    _host_entry as _host_entry,
    _out_of_memory as _out_of_memory,
    _refused_from as _refused_from,
    _run_bounded as _run_bounded,
    _run_in_process as _run_in_process,
    _run_program as _run_program,
    _safe_grants as _safe_grants,
    _secrets_named as _secrets_named,
    _source_to_file as _source_to_file,
    _spawn_capped as _spawn_capped,
    _unfinished_audit as _unfinished_audit,
    audit as audit,
    card as card,
    check as check,
    memory_cap_is_enforced as memory_cap_is_enforced,
    run as run,
)
from .pool import (  # noqa: E402
    MUTABLE_GLOBALS as MUTABLE_GLOBALS,
    Pool as Pool,
    PoolRegistry as PoolRegistry,
    _POOLS as _POOLS,
    _Worker as _Worker,
    _close_pools_at_exit as _close_pools_at_exit,
    _kill_workers as _kill_workers,
    _msg_read as _msg_read,
    _msg_write as _msg_write,
    _read_exactly as _read_exactly,
    pool_worker as pool_worker,
    program_state_baseline as program_state_baseline,
    reset_program_state as reset_program_state,
)
from .findings import (  # noqa: E402
    ERRORS_PAGE as ERRORS_PAGE,
    INVOCATION_SCHEMA as INVOCATION_SCHEMA,
    InvocationLog as InvocationLog,
    REPOSITORY as REPOSITORY,
    SARIF_FINDINGS as SARIF_FINDINGS,
    SARIF_SCHEMA_URI as SARIF_SCHEMA_URI,
    _EFFECT_WORDS as _EFFECT_WORDS,
    _SarifRun as _SarifRun,
    _own_functions as _own_functions,
    _sarif_coverage as _sarif_coverage,
    _sarif_errors as _sarif_errors,
    _sarif_unproven as _sarif_unproven,
    _unshown_loops as _unshown_loops,
    print_sarif_summary as print_sarif_summary,
    run_outcome as run_outcome,
    run_refusals as run_refusals,
    sarif_audit as sarif_audit,
    sarif_check as sarif_check,
    sarif_proofs as sarif_proofs,
    sarif_rules as sarif_rules,
)
from .mcp_manifest import (  # noqa: E402
    MCP_TOOLS_SCHEMA as MCP_TOOLS_SCHEMA,
    OIDC_ISSUER as OIDC_ISSUER,
    RELEASED_FROM_MAIN as RELEASED_FROM_MAIN,
    RELEASE_IDENTITY as RELEASE_IDENTITY,
    RELEASE_IDENTITY_MAIN as RELEASE_IDENTITY_MAIN,
    _canonical_json as _canonical_json,
    _default_mcp_command as _default_mcp_command,
    _sigstore_verify as _sigstore_verify,
    _split_server_command as _split_server_command,
    mcp_list_tools as mcp_list_tools,
    mcp_manifest_main as mcp_manifest_main,
    mcp_tool_hashes as mcp_tool_hashes,
    mcp_tool_manifest as mcp_tool_manifest,
    mcp_verify_main as mcp_verify_main,
    release_identity as release_identity,
)
from .doors import (  # noqa: E402
    DOOR_MAX_MEMORY_MB as DOOR_MAX_MEMORY_MB,
    DOOR_MAX_TIMEOUT as DOOR_MAX_TIMEOUT,
    DOOR_RATE_LIMIT as DOOR_RATE_LIMIT,
    _RateLimit as _RateLimit,
    _read_token_file as _read_token_file,
    _token_matches as _token_matches,
    _token_problem as _token_problem,
    check_ceilings as check_ceilings,
    door_ceilings as door_ceilings,
    run_limits as run_limits,
    serve_main as serve_main,
)
from .migrate import (  # noqa: E402
    MIGRATE_LINE as MIGRATE_LINE,
    MIGRATE_TO as MIGRATE_TO,
    MIGRATE_UNSURE as MIGRATE_UNSURE,
    MIGRATE_WRITABLE as MIGRATE_WRITABLE,
    _RUNNER as _RUNNER,
    _migrate_rewrite as _migrate_rewrite,
    migrate_main as migrate_main,
    migrate_needs as migrate_needs,
)
from .ratchet import (  # noqa: E402
    CAPABILITIES_CHECK_SCHEMA as CAPABILITIES_CHECK_SCHEMA,
    CAPABILITIES_FILE as CAPABILITIES_FILE,
    CAPABILITIES_SCHEMA as CAPABILITIES_SCHEMA,
    COUNTED_EFFECTS as COUNTED_EFFECTS,
    REVIEW_SCHEMA as REVIEW_SCHEMA,
    _BOUND_LIMIT as _BOUND_LIMIT,
    _OPERATIONS as _OPERATIONS,
    _PLAIN_EFFECTS as _PLAIN_EFFECTS,
    _as_count as _as_count,
    _because as _because,
    _call_sites as _call_sites,
    _capability_files as _capability_files,
    _chain as _chain,
    _const_int as _const_int,
    _count_exceeds as _count_exceeds,
    _covered as _covered,
    _covers as _covers,
    _declared_change as _declared_change,
    _effect_of as _effect_of,
    _effect_sites as _effect_sites,
    _finding_lines as _finding_lines,
    _git as _git,
    _grant_parts as _grant_parts,
    _literals_named as _literals_named,
    _needs as _needs,
    _norm_path as _norm_path,
    _operation_bounds as _operation_bounds,
    _path_covers as _path_covers,
    _program_capabilities as _program_capabilities,
    _reduce_grants as _reduce_grants,
    _review_side as _review_side,
    _shown_path as _shown_path,
    _site as _site,
    _text_constants as _text_constants,
    _text_value as _text_value,
    _turns as _turns,
    _version_tuple as _version_tuple,
    capabilities_compare as capabilities_compare,
    capabilities_document as capabilities_document,
    capabilities_main as capabilities_main,
    capabilities_text as capabilities_text,
    capability_scan as capability_scan,
    read_capabilities as read_capabilities,
    review as review,
    review_main as review_main,
    sarif_capabilities as sarif_capabilities,
)
from .conform import (  # noqa: E402
    CONFORMANCE_LEVELS as CONFORMANCE_LEVELS,
    CONFORMANCE_SCHEMA as CONFORMANCE_SCHEMA,
    CORPUS_FORMAT as CORPUS_FORMAT,
    _CONFORMANCE_KINDS as _CONFORMANCE_KINDS,
    _CONF_REFUSAL as _CONF_REFUSAL,
    _Skip as _Skip,
    _conf_audit as _conf_audit,
    _conf_bound as _conf_bound,
    _conf_budget as _conf_budget,
    _conf_budget_shape as _conf_budget_shape,
    _conf_check as _conf_check,
    _conf_covers as _conf_covers,
    _conf_derive as _conf_derive,
    _conf_edit as _conf_edit,
    _conf_files as _conf_files,
    _conf_invalid as _conf_invalid,
    _conf_ratchet as _conf_ratchet,
    _conf_reduce as _conf_reduce,
    _conf_resolved as _conf_resolved,
    _conf_run as _conf_run,
    _conf_sequence as _conf_sequence,
    _conf_servers as _conf_servers,
    _conf_validator as _conf_validator,
    _conf_verdict_wrong as _conf_verdict_wrong,
    _conf_write_baseline as _conf_write_baseline,
    _conf_write_guard as _conf_write_guard,
    _conformance_corpus as _conformance_corpus,
    _conformance_verdict as _conformance_verdict,
    conformance as conformance,
    conformance_main as conformance_main,
)
from .attestation import (  # noqa: E402
    CAPABILITY_SPEC as CAPABILITY_SPEC,
    INTOTO_STATEMENT_TYPE as INTOTO_STATEMENT_TYPE,
    _attest as _attest,
    _attested_at as _attested_at,
    _sha256_of as _sha256_of,
    _subject_name as _subject_name,
    attest as attest,
    attest_main as attest_main,
    attest_statement as attest_statement,
)
from .receipts import (  # noqa: E402
    _receipt_subjects as _receipt_subjects,
    _run_parameters as _run_parameters,
    receipt_statement as receipt_statement,
)
from .upgrades import (  # noqa: E402
    DEPS_COMMENT_MARKER as DEPS_COMMENT_MARKER,
    DEPS_DIFF_SCHEMA as DEPS_DIFF_SCHEMA,
    DEPS_LOCKFILES_SCHEMA as DEPS_LOCKFILES_SCHEMA,
    DEPS_SOURCES as DEPS_SOURCES,
    DepsError as DepsError,
    _CODE_LANGUAGES as _CODE_LANGUAGES,
    _DEPS_ARTIFACT_LIMIT as _DEPS_ARTIFACT_LIMIT,
    _DEPS_MAX_UPGRADES as _DEPS_MAX_UPGRADES,
    _DEPS_TREE_LIMIT as _DEPS_TREE_LIMIT,
    _LOCKFILES as _LOCKFILES,
    _LOCKFILES_NOT_READ as _LOCKFILES_NOT_READ,
    _NPM_INSTALL_SCRIPTS as _NPM_INSTALL_SCRIPTS,
    _RESERVED_NAMES as _RESERVED_NAMES,
    _archive_files as _archive_files,
    _clean_tree as _clean_tree,
    _code_counts as _code_counts,
    _declared_diff as _declared_diff,
    _deps_finding_lines as _deps_finding_lines,
    _deps_gained as _deps_gained,
    _deps_get as _deps_get,
    _deps_result as _deps_result,
    _deps_sarif_add as _deps_sarif_add,
    _deps_scan as _deps_scan,
    _deps_source as _deps_source,
    _deps_velaris as _deps_velaris,
    _describe_code as _describe_code,
    _git_repository as _git_repository,
    _github as _github,
    _grouped as _grouped,
    _hook_key as _hook_key,
    _hook_text as _hook_text,
    _hooks_diff as _hooks_diff,
    _lock_changes as _lock_changes,
    _lock_line as _lock_line,
    _lockfile_format as _lockfile_format,
    _md as _md,
    _md_text as _md_text,
    _missing as _missing,
    _named_files as _named_files,
    _npm_declared as _npm_declared,
    _npm_hooks as _npm_hooks,
    _package_base_uri as _package_base_uri,
    _parse_lockfile as _parse_lockfile,
    _pep508_name as _pep508_name,
    _python_hooks as _python_hooks,
    _read_dir as _read_dir,
    _read_git as _read_git,
    _read_npm as _read_npm,
    _read_pypi as _read_pypi,
    _requirements_map as _requirements_map,
    _sha256 as _sha256,
    _toml_value as _toml_value,
    _tree_declared as _tree_declared,
    _vendored_diff as _vendored_diff,
    _ver_key as _ver_key,
    deps_comment as deps_comment,
    deps_diff as deps_diff,
    deps_diff_lines as deps_diff_lines,
    deps_diff_main as deps_diff_main,
    deps_markdown as deps_markdown,
    deps_review as deps_review,
    deps_review_lines as deps_review_lines,
    sarif_deps_diff as sarif_deps_diff,
    sarif_deps_review as sarif_deps_review,
)
from .stats import (  # noqa: E402
    STATS_FFI_SCHEMA as STATS_FFI_SCHEMA,
    stats_ffi as stats_ffi,
    stats_ffi_lines as stats_ffi_lines,
    stats_main as stats_main,
)
from .eject import (  # noqa: E402
    EJECT_SCHEMA as EJECT_SCHEMA,
    _EJECT_BUILD as _EJECT_BUILD,
    _EJECT_LAUNCHER as _EJECT_LAUNCHER,
    _EJECT_README as _EJECT_README,
    _eject_write_reach as _eject_write_reach,
    _velaris_license as _velaris_license,
    eject_main as eject_main,
)
from .permissions import (  # noqa: E402
    PERMISSIONS_RATCHET_SCHEMA as PERMISSIONS_RATCHET_SCHEMA,
    PERMISSION_LEVELS as PERMISSION_LEVELS,
    PERMISSION_SCOPES as PERMISSION_SCOPES,
    WorkflowUnreadable as WorkflowUnreadable,
    permissions_compare as permissions_compare,
    permissions_exit as permissions_exit,
    permissions_lines as permissions_lines,
    permissions_main as permissions_main,
    permissions_ratchet as permissions_ratchet,
    read_workflow as read_workflow,
)
from .cli import (  # noqa: E402
    HELP_FLAGS as HELP_FLAGS,
    NO_CACHE_NOTICE as NO_CACHE_NOTICE,
    _check_ceiling as _check_ceiling,
    _cli_run as _cli_run,
    _cli_run_with_receipt as _cli_run_with_receipt,
    main as main,
    print_usage as print_usage,
    usage_lines as usage_lines,
)


def _bind_forward() -> None:
    """Give each module the names it takes from modules after it."""
    for name in _MODULES:
        module = _sys.modules[f"{__name__}.{name}"]
        for used, owner in getattr(module, "__forward__", {}).items():
            setattr(module, used,
                    getattr(_sys.modules[f"{__name__}.{owner}"], used))


_bind_forward()


def __getattr__(name: str) -> _typing.Any:
    """The run state, read where it lives: velaris.EFFECT_BUDGET is
    velaris.state.EFFECT_BUDGET as it is at this moment."""
    if not name.startswith("__") and name in vars(state):
        return getattr(state, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | {n for n in vars(state)
                                    if not n.startswith("__")})


class _Package(_types.ModuleType):
    """This package, as a module whose run-state names are written where
    they are read. Until 8.1.1 `velaris.IMPORT_ROOT = root` set the one
    file's global, which the runtime read; in the package it set an
    attribute nothing read, and imports silently stopped being confined (the
    8.2 adversarial pass). A write to a name velaris.state holds now reaches
    velaris.state, as a read does."""

    def __setattr__(self, name: str, value: _typing.Any) -> None:
        if not name.startswith("__") and name in vars(state)                 and name not in self.__dict__:
            setattr(state, name, value)
            return
        super().__setattr__(name, value)


_sys.modules[__name__].__class__ = _Package
