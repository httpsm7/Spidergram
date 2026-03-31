"""
e06_api_discoverer.py — REST / GraphQL / WebSocket Endpoint Discoverer
Uses ffuf wordlist fuzzing + JS mining + common patterns
MilkyWay Intelligence | Author: Sharlix
"""
import asyncio
import json
import os
import re
from typing import Dict, List
from urllib.parse import urljoin, urlparse
from protocols.http_client import HTTPClient
from core.format_fixer import FormatFixer

# Common API path prefixes to fuzz
API_PREFIXES = [
    "/api", "/api/v1", "/api/v2", "/api/v3",
    "/v1", "/v2", "/v3", "/rest", "/service",
    "/graphql", "/gql", "/query",
    "/ws", "/websocket", "/socket.io",
    "/swagger.json", "/openapi.json", "/api-docs",
    "/.well-known/openid-configuration",
]

# Common REST endpoints after prefix
REST_PATHS = [
    "/users", "/user", "/me", "/profile",
    "/auth", "/login", "/logout", "/register", "/signup",
    "/token", "/refresh", "/verify",
    "/admin", "/dashboard",
    "/orders", "/order", "/products", "/product",
    "/payment", "/payments", "/checkout",
    "/upload", "/download", "/files",
    "/search", "/settings", "/config",
    "/health", "/status", "/ping",
]

GQL_INTROSPECTION = {
    "query": """
{
  __schema {
    queryType { name }
    mutationType { name }
    types {
      name
      kind
      fields { name type { name kind ofType { name kind } } }
    }
  }
}
"""
}


class APIDiscovererEngine:
    def __init__(self, db, logger, http: HTTPClient,
                 out_dir: str, prefix: str):
        self.db      = db
        self.log     = logger
        self.http    = http
        self.out_dir = out_dir
        self.prefix  = prefix

    async def run(self, base_url: str) -> Dict:
        self.log.phase("API DISCOVERY")
        result = {
            "rest_endpoints": [],
            "graphql_schema": None,
            "websocket_endpoints": [],
            "total_new": 0
        }

        base = base_url.rstrip("/")
        self.log.info(f"API Discovery: {base}")

        # 1. Common prefix probe
        found_rest  = await self._probe_rest(base)
        result["rest_endpoints"].extend(found_rest)

        # 2. GraphQL detection + introspection
        gql_data = await self._probe_graphql(base)
        if gql_data:
            result["graphql_schema"] = gql_data

        # 3. WebSocket detection
        ws_eps = await self._probe_websocket(base)
        result["websocket_endpoints"].extend(ws_eps)

        # 4. ffuf-style wordlist fuzz (async lightweight)
        fuzz_eps = await self._lightweight_fuzz(base)
        result["rest_endpoints"].extend(fuzz_eps)

        # 5. Swagger/OpenAPI auto-import
        await self._import_openapi(base)

        # Deduplicate and add to graph
        all_eps = list({e["url"] for e in result["rest_endpoints"]})
        for url in all_eps:
            ntype    = FormatFixer.classify_url(url)
            priority = FormatFixer.priority_for_type(ntype)
            self.db.add_node(
                url=url, method=["GET", "POST"],
                params=[], node_type=ntype, priority=priority
            )

        result["total_new"] = len(all_eps)
        self.log.success(
            f"API Discovery: {len(found_rest)} REST, "
            f"{'GraphQL ✓' if result['graphql_schema'] else 'no GQL'}, "
            f"{len(ws_eps)} WS endpoints"
        )
        return result

    async def _probe_rest(self, base: str) -> List[Dict]:
        found = []
        tasks = []
        for prefix in API_PREFIXES:
            for path in REST_PATHS[:10]:
                url = base + prefix + path
                tasks.append(self._check_url(url))
            # Also try prefix alone
            tasks.append(self._check_url(base + prefix))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for url, ok in zip(
            [base + p + r for p in API_PREFIXES for r in list(REST_PATHS[:10]) + [""]][:len(results)],
            results
        ):
            if ok and not isinstance(ok, Exception):
                found.append({"url": url, "methods": ["GET", "POST"]})
        return found

    async def _check_url(self, url: str) -> bool:
        resp = await self.http.get(url, retries=1)
        return bool(resp and resp.status_code not in (404, 410, 503, 400))

    async def _probe_graphql(self, base: str) -> Dict:
        for suffix in ["/graphql", "/gql", "/query", "/api/graphql", "/graphql/v1"]:
            url  = base + suffix
            resp = await self.http.post(
                url,
                json_data=GQL_INTROSPECTION,
                extra_headers={"Content-Type": "application/json"},
                retries=1
            )
            if not resp or resp.status_code not in (200, 201):
                continue
            try:
                data = resp.json()
                if "__schema" in str(data):
                    self.log.success(f"GraphQL found: {url}")
                    self.db.add_node(
                        url=url, method=["POST"],
                        params=["query", "variables"],
                        node_type="GRAPHQL", priority=8
                    )
                    # Extract all types and fields as potential IDOR targets
                    self._process_graphql_schema(data, base)
                    return data
            except Exception:
                pass
        return {}

    def _process_graphql_schema(self, schema: Dict, base: str):
        """Add GraphQL queries/mutations as testable nodes."""
        try:
            types = schema.get("data", {}).get("__schema", {}).get("types", [])
            for t in types:
                if t.get("kind") == "OBJECT" and not t["name"].startswith("__"):
                    for field in (t.get("fields") or []):
                        fname = field.get("name", "")
                        if fname:
                            # Mark as testable endpoint
                            self.db.add_node(
                                url=f"{base}/graphql#{t['name']}.{fname}",
                                method=["POST"],
                                params=["id", "query"],
                                node_type="GRAPHQL", priority=7
                            )
        except Exception:
            pass

    async def _probe_websocket(self, base: str) -> List[Dict]:
        found = []
        ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
        for suffix in ["/ws", "/websocket", "/socket.io", "/cable", "/ws/v1"]:
            # Check via HTTP upgrade header detection
            resp = await self.http.get(
                base + suffix,
                extra_headers={"Upgrade": "websocket",
                               "Connection": "Upgrade",
                               "Sec-WebSocket-Version": "13",
                               "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ=="},
                retries=1
            )
            if resp and resp.status_code in (101, 200, 301, 302):
                url = ws_base + suffix
                found.append({"url": url, "type": "WEBSOCKET"})
                self.db.add_node(
                    url=base + suffix,
                    method=["GET"],
                    params=[],
                    node_type="WEBSOCKET", priority=7
                )
                self.log.info(f"WebSocket detected: {url}")
        return found

    async def _lightweight_fuzz(self, base: str) -> List[Dict]:
        """Async lightweight fuzzer using common API words."""
        WORDLIST = [
            "api", "admin", "user", "users", "auth", "login", "register",
            "logout", "signup", "profile", "me", "account", "accounts",
            "order", "orders", "product", "products", "payment", "payments",
            "checkout", "cart", "item", "items", "search", "upload", "file",
            "files", "document", "documents", "report", "reports", "config",
            "settings", "webhook", "callback", "token", "keys", "health",
            "status", "metrics", "internal", "private", "secret", "debug",
            "test", "staging", "dev", "backup", "export", "import",
        ]
        found = []
        sem   = asyncio.Semaphore(10)

        async def probe(word):
            async with sem:
                for url in [f"{base}/{word}", f"{base}/api/{word}"]:
                    resp = await self.http.get(url, retries=1)
                    if resp and resp.status_code not in (404, 410, 503):
                        return {"url": url, "status": resp.status_code}
            return None

        results = await asyncio.gather(
            *[probe(w) for w in WORDLIST], return_exceptions=True
        )
        for r in results:
            if r and not isinstance(r, Exception):
                found.append(r)
        return found

    async def _import_openapi(self, base: str):
        """Import OpenAPI/Swagger spec if available."""
        for spec_url in [
            f"{base}/swagger.json",
            f"{base}/openapi.json",
            f"{base}/api-docs",
            f"{base}/api/swagger.json",
            f"{base}/v1/swagger.json",
            f"{base}/.well-known/openid-configuration",
        ]:
            resp = await self.http.get(spec_url, retries=1)
            if not resp or resp.status_code != 200:
                continue
            try:
                spec = resp.json()
                paths = spec.get("paths", {})
                if paths:
                    self.log.success(
                        f"OpenAPI spec found: {spec_url} ({len(paths)} paths)"
                    )
                    servers = spec.get("servers", [{}])
                    server  = servers[0].get("url", "") if servers else ""
                    for path, methods in paths.items():
                        full_url = urljoin(base, path) if not path.startswith("http") else path
                        http_methods = [m.upper() for m in methods.keys()
                                        if m.upper() in ("GET","POST","PUT",
                                                          "DELETE","PATCH")]
                        # Extract params from spec
                        params = []
                        for mdata in methods.values():
                            if isinstance(mdata, dict):
                                for p in mdata.get("parameters", []):
                                    if isinstance(p, dict) and "name" in p:
                                        params.append(p["name"])
                        ntype    = FormatFixer.classify_url(full_url)
                        priority = FormatFixer.priority_for_type(ntype)
                        self.db.add_node(
                            url=full_url,
                            method=http_methods or ["GET"],
                            params=params,
                            node_type=ntype, priority=priority
                        )
                    return
            except Exception:
                pass
