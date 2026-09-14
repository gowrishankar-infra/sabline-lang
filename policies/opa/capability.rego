# What a policy asks of a Velaris capability attestation.
#
# Input: an in-toto Statement v1 whose predicate type is
#   https://gowrishankar-infra.github.io/velaris-lang/capability/v1
# which is what `velaris attest program.vel` writes (velaris-spec 8.5):
# the audit of a program, bound to its bytes by sha256.
#
# Data: the platform's allow-lists,
#   {"platform": {"effects": ["io", "net"],
#                 "hosts": ["api.example.com", "*.cdn.example.net:443"]}}
# An effect is one of Velaris's names (io, env, fs, net, clock, rand, ffi,
# declassify). A host entry is written as velaris.audit/1 writes a host:
# lower-case, `host` or `host:port`, an IPv6 address in brackets. An entry
# without a port admits that host on any port; `*.example.com` admits one
# label in place of the star, and not example.com itself.
#
# `deny` is the set of reasons to refuse. An empty set admits the program.
# Besides the two allow-lists it refuses what it cannot check: an audit of
# a program that did not compile bounds nothing, and a host built while the
# program runs cannot be held to a list.
#
#   opa eval -d capability.rego -d platform.json -i app.intoto.json \
#       'data.velaris.capability.deny'
#   conftest test app.intoto.json -p capability.rego \
#       --namespace velaris.capability -d platform.json
package velaris.capability

import rego.v1

predicate_type := "https://gowrishankar-infra.github.io/velaris-lang/capability/v1"

default allowed_effects := {"io"}

allowed_effects := {e | some e in data.platform.effects} if data.platform.effects

default allowed_hosts := set()

allowed_hosts := {h | some h in data.platform.hosts} if data.platform.hosts

audit := object.get(input, ["predicate", "audit"], {})

deny contains msg if {
	input.predicateType != predicate_type
	msg := sprintf("the predicate type is %v, not %v", [input.predicateType, predicate_type])
}

deny contains "the audit's program did not compile, so the audit bounds nothing" if {
	object.get(audit, "ok", false) != true
}

deny contains msg if {
	some effect in object.get(audit, "effects", [])
	not effect in allowed_effects
	msg := sprintf("effect %v is outside the allowed set %v", [effect, sort(allowed_effects)])
}

deny contains msg if {
	some host in object.get(audit, ["net_hosts", "hosts"], [])
	not host_allowed(host)
	msg := sprintf("net host %v is outside the allow-list", [host])
}

deny contains "a net host is built while the program runs, so it cannot be held to the allow-list" if {
	object.get(audit, ["net_hosts", "any"], false) == true
}

# `host` or `host:port`; an IPv6 host keeps its brackets
parts(entry) := {"host": m[1], "port": m[2]} if {
	m := regex.find_all_string_submatch_n(`^(\[[^\]]*\]|[^:\[\]]+)(?::([0-9]+))?$`, entry, 1)[0]
}

host_allowed(entry) if {
	some allowed in allowed_hosts
	a := parts(allowed)
	h := parts(entry)
	name_matches(a.host, h.host)
	port_matches(a.port, h.port)
}

name_matches(pattern, name) if pattern == name

name_matches(pattern, name) if {
	startswith(pattern, "*.")
	tail := substring(pattern, 1, -1)
	endswith(name, tail)
	label := trim_suffix(name, tail)
	label != ""
	not contains(label, ".")
}

# an allow-list entry that names no port admits any port
port_matches(allowed, _) if allowed == ""

port_matches(allowed, given) if {
	allowed != ""
	allowed == given
}
