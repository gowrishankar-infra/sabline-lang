# opa test policies/opa   (or: conftest verify -p policies/opa)
package sabline.capability_test

import rego.v1

import data.sabline.capability

platform := {"effects": ["io", "net"], "hosts": ["api.example.com", "*.cdn.example.net:443"]}

statement(ok, effects, hosts, any) := {
	"_type": "https://in-toto.io/Statement/v1",
	"subject": [{"name": "app.vel", "digest": {"sha256": "0000000000000000000000000000000000000000000000000000000000000000"}}],
	"predicateType": "https://sabline.dev/capability/v1",
	"predicate": {
		"producer": {"name": "sabline-lang"},
		"audit": {
			"schema": "sabline.audit/1",
			"ok": ok,
			"effects": effects,
			"net_hosts": {"hosts": hosts, "any": any},
			"safe_command": "sabline <file> --allow io,net",
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

# a Statement written by Sabline 4.2 to 8.2.1 names the type at the project's
# GitHub Pages address: the same type
test_admits_the_type_as_written_before_8_3 if {
	count(capability.deny) == 0 with input as object.union(statement(true, ["io"], [], false), {"predicateType": "https://gowrishankar-infra.github.io/velaris-lang/capability/v1"})
		with data.platform as platform
}

# and one written by 8.3 to 8.5 names it at velaris-lang.dev, the domain the
# project held before it was renamed Sabline in 8.6: also the same type
test_admits_the_type_as_written_before_8_6 if {
	count(capability.deny) == 0 with input as object.union(statement(true, ["io"], [], false), {"predicateType": "https://velaris-lang.dev/capability/v1"})
		with data.platform as platform
}

# velaris.dev was never this project's domain, and neither is velaris.io, the
# company whose name it gave up: a type under either is another type
test_refuses_the_type_under_a_domain_sabline_does_not_hold if {
	some msg in capability.deny with input as object.union(statement(true, ["io"], [], false), {"predicateType": "https://velaris.dev/capability/v1"})
		with data.platform as platform
	startswith(msg, "the predicate type is")
}

test_refuses_the_type_under_the_company_it_was_named_after if {
	some msg in capability.deny with input as object.union(statement(true, ["io"], [], false), {"predicateType": "https://velaris.io/capability/v1"})
		with data.platform as platform
	startswith(msg, "the predicate type is")
}

test_with_no_data_only_io_is_allowed if {
	count(capability.deny) == 0 with input as statement(true, ["io"], [], false)
	count(capability.deny) == 1 with input as statement(true, ["io", "net"], [], false)
}
