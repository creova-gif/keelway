from tests.test_proof_strip_ux import STUDIO_JS, run_node_eval


def test_gate_clock_and_strings():
    out = run_node_eval("const g = (helpers && helpers.gateClock) || window.gateClock; return { a: g(300), b: g(59.2), c: g(-3) };")
    assert out == {"a": "5:00", "b": "1:00", "c": "0:00"}


def test_gate_card_contract_in_source():
    js = STUDIO_JS.read_text(encoding="utf-8")
    assert "'/v1/gate/pending'" in js and "/v1/gate/deny-waiting" in js
    assert "gateDenyAll: 'Deny all waiting'" in js and "Allow all" not in js
    assert "'aria-live': 'polite'" in js and "min-height:44px" in js
    assert "gateUi.milestones.has(60)" in js and "gateUi.milestones.has(10)" in js
    assert "h('bdi', { dir: 'ltr' }, `$ ${shown}`)" in js
