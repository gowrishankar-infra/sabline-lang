//! The canonical check document: what `sabline check` finds in one file,
//! as `sabline/check_dump.py` writes it, key for key.
//!
//! It is a comparison surface and nothing else - `check_agreement.py`
//! compares it with the Python package's, stage by stage - and rt/README.md
//! states the format. The stages are the reference's, in the reference's
//! order: the loader, `main` as a check asks about it and as a run does,
//! the effect checker, and the type checker, which runs only when the three
//! before it found nothing. Then every problem once, and every loop's
//! termination verdict. There is no prover stage: sabline-rt does not
//! prove (decisions/0002).

use std::collections::{HashMap, HashSet};

use crate::checker::{check_main, check_types};
use crate::effects::check_effects;
use crate::errors::SablineError;
use crate::json::Json;
use crate::loader::load_program;
use crate::nodes::Function;
use crate::termination::loop_termination;

/// The format's version, carried in every document.
pub const CHECK_VERSION: i64 = 1;

fn error_json(e: &SablineError, path: &str) -> Json {
    Json::obj([
        ("code", Json::text(e.code)),
        ("file", Json::text(e.file.clone().unwrap_or_else(|| path.to_string()))),
        ("fixes", Json::List(e.fixes.iter().map(|f| Json::text(f.clone())).collect())),
        ("line", Json::Int(i64::from(e.line))),
        ("message", Json::text(e.message.clone())),
    ])
}

fn list(errors: &[SablineError], path: &str) -> Json {
    Json::List(errors.iter().map(|e| error_json(e, path)).collect())
}

/// The document for one file, staged as `sabline check` runs it.
pub fn check_document(path: &str, install_dir: &str) -> Json {
    let loaded = match load_program(path, install_dir) {
        Ok(loaded) => loaded,
        Err(e) => {
            let one = error_json(&e, path);
            return Json::obj([
                ("check", Json::Int(CHECK_VERSION)),
                ("errors", Json::List(vec![one.clone()])),
                ("loops", Json::List(Vec::new())),
                (
                    "stages",
                    Json::obj([
                        ("load", one),
                        ("main", Json::Null),
                        ("main_run", Json::Null),
                        ("effects", Json::Null),
                        ("types", Json::Null),
                    ]),
                ),
            ]);
        }
    };
    let funcs = &loaded.funcs;
    let mut main = Vec::new();
    check_main(funcs, &mut main, false);
    let mut main_run = Vec::new();
    check_main(funcs, &mut main_run, true);
    let mut effects = Vec::new();
    check_effects(funcs, install_dir, &mut effects);
    let mut found: Vec<SablineError> = main.iter().chain(&effects).cloned().collect();
    let mut types: Option<Vec<SablineError>> = None;
    if found.is_empty() {
        let mut ran = Vec::new();
        if let Err(raised) = check_types(funcs, &loaded.records, &mut ran) {
            ran.push(raised); // a raise is still one problem
        }
        found.clone_from(&ran);
        types = Some(ran);
    }

    let mut seen: HashSet<(&'static str, String, u32, String)> = HashSet::new();
    let mut errors = Vec::new();
    for e in &found {
        let key = (
            e.code,
            e.file.clone().unwrap_or_else(|| path.to_string()),
            e.line,
            e.message.clone(),
        );
        if seen.insert(key) {
            errors.push(error_json(e, path));
        }
    }

    let table: HashMap<&str, &Function> = funcs.iter().map(|f| (f.name.as_str(), f)).collect();
    let mut loops = Vec::new();
    for f in funcs {
        let file = if f.src_file.is_empty() { path.to_string() } else { f.src_file.clone() };
        for v in loop_termination(f, &table) {
            loops.push(Json::obj([
                ("function", Json::text(f.name.clone())),
                ("file", Json::text(file.clone())),
                ("line", Json::Int(i64::from(v.line))),
                ("verdict", Json::text(v.verdict)),
                ("why", Json::text(v.why)),
            ]));
        }
    }

    Json::obj([
        ("check", Json::Int(CHECK_VERSION)),
        ("errors", Json::List(errors)),
        ("loops", Json::List(loops)),
        (
            "stages",
            Json::obj([
                ("load", Json::Null),
                ("main", list(&main, path)),
                ("main_run", list(&main_run, path)),
                ("effects", list(&effects, path)),
                ("types", types.as_deref().map_or(Json::Null, |t| list(t, path))),
            ]),
        ),
    ])
}

/// Whether a document found no problem.
pub fn checked_clean(document: &Json) -> bool {
    matches!(document, Json::Obj(fields)
        if matches!(fields.get("errors"), Some(Json::List(items)) if items.is_empty()))
}
