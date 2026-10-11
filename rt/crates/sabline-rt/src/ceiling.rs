//! The organisation ceiling (9.0, M3; decisions/0007, item 32c):
//! `sabline/ceiling.py`, ported - a file whoever administers a machine
//! installs, capping what any budget on it may grant.
//!
//! **What sabline-rt is given** is the ceiling's text and where it was read
//! from, never the file: the Python package finds it (its one system path,
//! and `SABLINE_CEILING`), holds the run to it first, and hands the text on
//! in the exec request; the gate's list gives the text in a line. Both
//! runtimes read a ceiling from that text the same way, hold the budget to
//! it the same way ([`crate::budget::Budget::gap`]), refuse it with the same
//! words, E325, and name it in the receipt's `run_parameters.ceilings` - its
//! path, the sha256 of its bytes and what it allows.
//!
//! A ceiling that cannot be read as one allows nothing: every run held to
//! it is refused, saying what is wrong with it.

use crate::budget::{expand_allow, Budget};
use crate::errors::SablineError;
use crate::json::Json;
use crate::pyjson;
use crate::text::Text;
use crate::value::Value;

/// `CEILING_SCHEMA`.
pub const CEILING_SCHEMA: &str = "sabline.ceiling/1";

/// `FIELDS`: what the file may hold.
pub const FIELDS: [&str; 3] = ["schema", "allow", "description"];

/// One ceiling, as read: where it came from, the sha256 of its bytes, and
/// the budget it allows - or why it is not one.
#[derive(Debug, Clone)]
pub struct Ceiling {
    /// Where it was read from, as the package names it.
    pub path: String,
    /// The sha256 of its bytes.
    pub sha256: String,
    /// What it allows; `Err` is why it is not a ceiling.
    pub allows: Result<Budget, String>,
}

impl Ceiling {
    /// What a receipt says of it: `{"path", "sha256", "allow"}`, `allow`
    /// null for one that is not a ceiling.
    pub fn receipt(&self) -> Json {
        Json::obj([
            ("path", Json::text(self.path.clone())),
            ("sha256", Json::text(self.sha256.clone())),
            ("allow", self.allows.as_ref().map_or(Json::Null, |b| Json::text(b.spec()))),
        ])
    }
}

/// `read(path, text)`: a ceiling from the text the file at `path` holds.
pub fn read(path: &str, text: &str) -> Ceiling {
    let sha256 = crate::digest::hex(&crate::digest::sha256(text.as_bytes()));
    let allows = parse(text);
    Ceiling { path: path.to_string(), sha256, allows }
}

fn parse(text: &str) -> Result<Budget, String> {
    let doc = pyjson::loads(&Text::from(text)).map_err(|e| format!("it is not JSON: {e}"))?;
    let Value::Map(doc) = doc else { return Err("it is not a JSON object".to_string()) };
    let field = |name: &str| doc.get(&Value::text(name)).ok().flatten().cloned();
    if !matches!(field("schema"), Some(Value::Text(s)) if s == Text::from(CEILING_SCHEMA)) {
        return Err(format!("it does not say \"schema\": \"{CEILING_SCHEMA}\""));
    }
    let mut unknown: Vec<Text> = doc
        .entries()
        .iter()
        .filter_map(|(k, _)| match k {
            Value::Text(t) if FIELDS.iter().any(|f| *t == Text::from(*f)) => None,
            other => Some(crate::value::py_str(other)),
        })
        .collect();
    unknown.sort();
    if let Some(first) = unknown.first() {
        return Err(format!(
            "'{}' is not a field of a ceiling (it holds {})",
            first.to_string_lossy(),
            FIELDS.join(", ")
        ));
    }
    let Some(Value::Text(allow)) = field("allow") else {
        return Err(
            "its \"allow\" is not a budget written as text, as \"io,fs:read:/srv/data\""
                .to_string(),
        );
    };
    let allow = allow.to_string_lossy();
    Budget::parse(&expand_allow(&allow))
        .map_err(|e| format!("its \"allow\" is not a budget: {}", e.0))
}

fn e325(message: String, fixes: Vec<String>) -> SablineError {
    SablineError { code: "E325", message, line: 0, fixes, file: None }
}

/// `refusal(ceilings, budget)`: E325 for the first ceiling that is not one
/// or does not cover all of `budget`, or `None` when every one does.
pub fn refusal(ceilings: &[Ceiling], budget: &Budget) -> Option<SablineError> {
    for c in ceilings {
        let held = match &c.allows {
            Err(why) => {
                return Some(e325(
                    format!(
                        "the organisation ceiling {} is not one, so no run on this machine can be \
                         held to it: {why}",
                        c.path
                    ),
                    vec![
                        format!(
                            "mend it: a ceiling is a JSON object, {{\"schema\": \"{CEILING_SCHEMA}\", \
                             \"allow\": \"io,fs:read:/srv/data\"}}"
                        ),
                        "until it is mended every run here is refused: a ceiling that cannot be \
                         read cannot be held"
                            .to_string(),
                        "sabline ceiling shows every ceiling installed here".to_string(),
                    ],
                ));
            }
            Ok(held) => held,
        };
        if let Some((effect, why)) = held.gap(budget) {
            let allows = held.spec();
            let shown = if allows.is_empty() { "nothing".to_string() } else { allows.clone() };
            let narrow = if allows.is_empty() {
                "the ceiling allows nothing, so no budget fits inside it".to_string()
            } else {
                format!("narrow the budget to fit inside it, as --allow {allows}")
            };
            return Some(e325(
                format!(
                    "the budget's '{effect}' grant goes past the organisation ceiling {}: {why} \
                     (it allows: {shown})",
                    c.path
                ),
                vec![
                    narrow,
                    format!(
                        "or ask whoever administers this machine to widen {}: nothing on the \
                         command line or in the program can",
                        c.path
                    ),
                    "sabline ceiling shows every ceiling installed here".to_string(),
                ],
            ));
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn budget(spec: &str) -> Budget {
        Budget::parse(spec).unwrap()
    }

    #[test]
    fn a_ceiling_reads_as_the_package_reads_one() {
        let ok = read("c.json", r#"{"schema": "sabline.ceiling/1", "allow": "io,net@3"}"#);
        assert_eq!(ok.allows.as_ref().map(Budget::spec).unwrap(), "io,net@3");
        assert_eq!(ok.sha256.len(), 64);
        let broken = |text: &str| read("c.json", text).allows.unwrap_err();
        assert_eq!(broken("{"), "it is not JSON: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)");
        assert_eq!(broken("[]"), "it is not a JSON object");
        assert!(broken(r#"{"allow": "io"}"#).starts_with("it does not say"));
        assert_eq!(
            broken(r#"{"schema": "sabline.ceiling/1", "allow": "io", "zz": 1, "b": 2}"#),
            "'b' is not a field of a ceiling (it holds schema, allow, description)"
        );
        assert!(broken(r#"{"schema": "sabline.ceiling/1", "allow": 3}"#)
            .contains("written as text"));
        assert!(broken(r#"{"schema": "sabline.ceiling/1", "allow": "io,wifi"}"#)
            .starts_with("its \"allow\" is not a budget: "));
        let all = read("c.json", r#"{"schema": "sabline.ceiling/1", "allow": "all"}"#);
        assert!(all.allows.unwrap().effects.contains("ffi"));
    }

    #[test]
    fn a_budget_inside_every_ceiling_runs_and_one_past_any_is_e325() {
        let ceilings = [
            read(
                "a.json",
                r#"{"schema": "sabline.ceiling/1", "allow": "io,fs,net:*.corp.com"}"#,
            ),
            read("b.json", r#"{"schema": "sabline.ceiling/1", "allow": "io,net@5,fs:read"}"#),
        ];
        assert!(refusal(&ceilings, &budget("io,fs:read,net:api.corp.com@2")).is_none());
        // either order gives the same verdict
        let reversed = [ceilings[1].clone(), ceilings[0].clone()];
        for budget_text in ["io,net:api.corp.com", "io,fs", "io,ffi", "io,net:x.other.com@1"] {
            assert_eq!(
                refusal(&ceilings, &budget(budget_text)).is_some(),
                refusal(&reversed, &budget(budget_text)).is_some(),
                "{budget_text}"
            );
        }
        let e = refusal(&ceilings, &budget("io,net:api.corp.com")).unwrap();
        assert_eq!(e.code, "E325");
        assert_eq!(
            e.message,
            "the budget's 'net' grant goes past the organisation ceiling b.json: it allows at \
             most 5 network operations (it allows: fs:read,io,net@5)"
        );
        let broken = [read("x.json", "nope")];
        assert!(refusal(&broken, &budget("io"))
            .unwrap()
            .message
            .contains("x.json is not one"));
    }
}
