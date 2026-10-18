import urllib.request
import json

def test_api(name, url, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
        body = json.dumps(data).encode()
    else:
        body = None
    with urllib.request.urlopen(req, data=body, timeout=5) as res:
        out = json.loads(res.read())
        print(f"=== {name} ===")
        if "elements" in out:
            print(f"Canvas elements count: {len(out['elements'])}")
        elif "timeline" in out:
            print(f"Simulated Incident: {out['incident_id']} ({out['severity']})")
            print(f"Steps executed: {len(out['timeline'])}")
            for step in out["timeline"]:
                print(f"  - Step {step['step']}: {step['agent']} -> {step['tool_called']}")
            print("Summary:", out.get("summary"))
        elif "result_set" in out:
            print(f"Cypher query success: {out.get('success')} in {out.get('execution_time_ms')}ms")
            print(f"Rows returned: {len(out.get('result_set', []))}")
            print(f"Results sample: {out.get('result_set', [])[:3]}")
        else:
            print(out)

test_api("STATUS", "http://127.0.0.1:8000/api/status")
test_api("CANVAS", "http://127.0.0.1:8000/api/graph/canvas")
test_api("INCIDENT SIMULATE", "http://127.0.0.1:8000/api/incident/simulate", "POST", {"service": "payment-service"})
test_api("CYPHER BLAST RADIUS", "http://127.0.0.1:8000/api/cypher/run", "POST", {"query": 'MATCH (s:Service {name: "payment-service"})<-[:DEPENDS_ON*1..3]-(impacted:Service) RETURN impacted.name AS service, length(path) as hops'})
test_api("SPOF PAGERANK", "http://127.0.0.1:8000/api/tools/spof_pagerank")
test_api("OWNERSHIP", "http://127.0.0.1:8000/api/tools/ownership/payment-service")
