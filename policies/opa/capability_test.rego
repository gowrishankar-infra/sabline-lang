# opa test policies/opa   (or: conftest verify -p policies/opa)
package velaris.capability_test

import rego.v1

import data.velaris.capability

platform := {"effects": ["io", "net"], "hosts": ["api.example.com", "*.cdn.example.net:443"]}

statement(ok, effects, hosts, any) := {
	"_type": "https://in-toto.io/Statement/v1",
	"subject": [{"name": "app.vel", "digest": {"sha256": "0000000000000000000000000000000000000000000000000000000000000000"}}],
	"predicateType": "https://gowrishankar-infra.github.io/velaris-lang/capability/v1",
	"predicate": {
		"producer": {"name": "velaris-lang"},
		"audit": {
			"schema": "velaris.audit/1",
			"ok": ok,
			"effects": effects,
			"net_hosts": {"hosts": hosts, "any": any},
			"safe_command": "velaris <file> --allow io,net",
		},
	},
}

# a pass: every effect and every host inside the lists
test_admits_a_program_inside_both_lists if {
	count(capability.deny) == 0 with input as statement(true, ["io", "net"], ["api.example.com:443", "img.cdn.example.net:443"], false)
		with data.platform as platform
}

# a fail: a host outside the allow-list
test_refuses_a_host_outside_the_allow_list if {
	capability.deny == {"net host collector.example.org is outside the allow-list"} with input as statement(true, ["io", "net"], ["api.example.com", "collector.example.org"], false)
		with data.platform as platform
}

# a fail: an effect outside the allowed set
test_refuses_an_effect_outside_the_allowed_set if {
	capability.deny == {`effect fs is outside the allowed set ["io", "net"]`} with input as statement(true, ["fs", "io"], [], false)
		with data.platform as platform
}

test_a_wildcard_is_one_label if {
	count(capability.deny) == 1 with input as statement(true, ["net"], ["a.b.cdn.example.net:443"], false)
		with data.platform as platform
	count(capability.deny) == 1 with input as statement(true, ["net"], ["cdn.example.net:443"], false)
		with data.platform as platform
}

test_a_port_the_entry_names_is_the_only_port if {
	count(capability.deny) == 1 with input as statement(true, ["net"], ["img.cdn.example.net:8443"], false)
		with data.platform as platform
}

test_refuses_a_host_built_while_running if {
	count(capability.deny) == 1 with input as statement(true, ["net"], [], true)
		with data.platform as platform
}

test_refuses_an_audit_that_did_not_compile if {
	count(capability.deny) == 1 with input as statement(false, [], [], false)
		with data.platform as platform
}

test_refuses_another_predicate_type if {
	some msg in capability.deny with input as object.union(statement(true, ["io"], [], false), {"predicateType": "https://slsa.dev/provenance/v1"})
		with data.platform as platform
	startswith(msg, "the predicate type is")
}

test_with_no_data_only_io_is_allowed if {
	count(capability.deny) == 0 with input as statement(true, ["io"], [], false)
	count(capability.deny) == 1 with input as statement(true, ["io", "net"], [], false)
}
