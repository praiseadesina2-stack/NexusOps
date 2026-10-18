import sys
from falkordb import FalkorDB

host = 'r-6jissuruar.instance-94olzko8f.hc-7up0crkyn.ap-south-1.aws.f2e0a955bb84.cloud'
port = 63782
password = 'Mobi21/m2007'

for ssl_val in [False, True]:
    for user_val in [None, 'default', 'falkor', 'admin']:
        print(f"Testing ssl={ssl_val}, username={user_val}...", flush=True)
        try:
            kwargs = {'host': host, 'port': port, 'password': password, 'socket_timeout': 3}
            if ssl_val:
                kwargs['ssl'] = True
            if user_val:
                kwargs['username'] = user_val
            db = FalkorDB(**kwargs)
            g = db.select_graph('test_graph')
            res = g.query("RETURN 'OK' AS status")
            print(f"SUCCESS with ssl={ssl_val}, username={user_val}: {res.result_set}", flush=True)
            sys.exit(0)
        except Exception as e:
            print(f"Failed ({type(e).__name__}): {e}", flush=True)
