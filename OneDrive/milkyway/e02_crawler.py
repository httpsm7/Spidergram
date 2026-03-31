"""
e02_crawler.py — Playwright Headless Browser + HTTP Fallback Crawler
FIX: Playwright timeout handled gracefully, HTTP fallback always works
MilkyWay Intelligence | Author: Sharlix
"""
import asyncio
import os
import re
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse
from core.format_fixer import FormatFixer


class CrawlerEngine:
    def __init__(self, db, logger, out_dir: str, prefix: str,
                 proxy: str = None, max_depth: int = 3,
                 max_pages: int = 100):
        self.db        = db
        self.logger    = logger
        self.out_dir   = out_dir
        self.prefix    = prefix
        self.proxy     = proxy
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.visited:  Set[str] = set()
        self.discovered: List[Dict] = []

    async def run(self, start_url: str,
                  session_cookies: Dict = None) -> Dict:
        self.logger.phase("CRAWLING")
        results = {"pages": [], "forms": [], "endpoints": [], "js_files": []}

        # Try Playwright first (longer timeout, graceful fail)
        playwright_ok = await self._try_playwright(
            start_url, session_cookies, results
        )

        if not playwright_ok:
            # Always fall back to HTTP crawler
            self.logger.warn("Playwright failed — using HTTP crawler")
            await self._http_crawl(start_url, session_cookies, results)

        # Add all discovered endpoints to graph DB
        added = 0
        for ep in results.get("endpoints", []):
            url_clean = ep.get("url", "").split("?")[0]
            if not url_clean:
                continue
            node_type = FormatFixer.classify_url(url_clean)
            priority  = FormatFixer.priority_for_type(node_type)
            params    = ep.get("params", [])
            methods   = ep.get("methods", ["GET"])
            self.db.add_node(
                url=url_clean, method=methods, params=params,
                node_type=node_type, priority=priority
            )
            added += 1

        # Also add all visited pages
        for page_url in self.visited:
            node_type = FormatFixer.classify_url(page_url)
            self.db.add_node(
                url=page_url, method=["GET"], params=[],
                node_type=node_type,
                priority=FormatFixer.priority_for_type(node_type)
            )

        _write(
            os.path.join(self.out_dir, f"{self.prefix}_crawled_urls.txt"),
            "\n".join(self.visited)
        )
        self.logger.success(
            f"Crawled {len(self.visited)} pages, "
            f"{added} endpoints discovered"
        )
        return results

    async def _try_playwright(self, start_url: str,
                               session_cookies: Dict,
                               results: Dict) -> bool:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return False

        try:
            async with async_playwright() as pw:
                args = ["--no-sandbox", "--disable-setuid-sandbox",
                        "--ignore-certificate-errors",
                        "--disable-web-security"]
                if self.proxy:
                    browser = await pw.chromium.launch(
                        headless=True, args=args,
                        proxy={"server": self.proxy}
                    )
                else:
                    browser = await pw.chromium.launch(
                        headless=True, args=args
                    )

                context = await browser.new_context(
                    ignore_https_errors=True,
                    java_script_enabled=True,
                )
                if session_cookies:
                    domain = urlparse(start_url).hostname
                    await context.add_cookies([
                        {"name": k, "value": v,
                         "domain": domain, "path": "/"}
                        for k, v in session_cookies.items()
                    ])

                page = await context.new_page()

                # Intercept requests
                captured = []
                async def handle_route(route):
                    req = route.request
                    url = req.url
                    if not any(url.endswith(ext) for ext in
                               [".css", ".png", ".jpg", ".gif",
                                ".ico", ".woff", ".svg", ".mp4"]):
                        params = self._url_params(url)
                        captured.append({
                            "url":     url.split("?")[0],
                            "methods": [req.method],
                            "params":  params,
                        })
                    await route.continue_()

                await page.route("**/*", handle_route)
                await self._crawl_page(
                    page, start_url, 0, results,
                    urlparse(start_url).hostname
                )
                results["endpoints"].extend(captured)
                await browser.close()
                return True

        except asyncio.TimeoutError:
            self.logger.warn("Playwright timeout — using HTTP fallback")
        except Exception as e:
            self.logger.warn(f"Playwright error: {str(e)[:80]}")
        return False

    async def _crawl_page(self, page, url: str, depth: int,
                           results: Dict, base_domain: str):
        if (url in self.visited or depth > self.max_depth
                or len(self.visited) >= self.max_pages):
            return
        self.visited.add(url)

        try:
            # Use longer timeout and domcontentloaded (faster than networkidle)
            await page.goto(url, timeout=20000,
                            wait_until="domcontentloaded")
            await asyncio.sleep(0.3)

            # Links
            links = await page.eval_on_selector_all(
                "a[href]", "els => els.map(e => e.href)"
            )

            # Forms
            forms = await page.eval_on_selector_all("form", """
                forms => forms.map(f => ({
                    action: f.action || '',
                    method: (f.method || 'GET').toUpperCase(),
                    inputs: Array.from(f.querySelectorAll(
                        'input,textarea,select'))
                        .map(i => ({name: i.name, type: i.type}))
                        .filter(i => i.name)
                }))
            """)
            for form in forms:
                results["forms"].append(form)
                action = form.get("action", url)
                if action:
                    params = [i["name"] for i in form.get("inputs", [])]
                    method = form.get("method", "GET")
                    self.db.add_node(
                        url=action.split("?")[0],
                        method=[method], params=params,
                        node_type=FormatFixer.classify_url(action)
                    )
                    results["endpoints"].append({
                        "url":     action.split("?")[0],
                        "methods": [method],
                        "params":  params
                    })

            # JS files
            js_srcs = await page.eval_on_selector_all(
                "script[src]", "els => els.map(e => e.src)"
            )
            results["js_files"].extend(js_srcs)

            # Recurse same-domain links
            for link in links:
                p = urlparse(link)
                if p.hostname == base_domain:
                    clean = link.split("#")[0].split("?")[0]
                    if clean not in self.visited:
                        results["pages"].append(clean)
                        await self._crawl_page(
                            page, clean, depth + 1,
                            results, base_domain
                        )

        except asyncio.TimeoutError:
            self.logger.warn(f"Timeout crawling {url[:60]}")
        except Exception as e:
            self.logger.warn(f"Crawl error {url[:50]}: {str(e)[:60]}")

    async def _http_crawl(self, start_url: str,
                           session_cookies: Dict,
                           results: Dict):
        """Pure HTTP fallback crawler — always works."""
        import httpx

        headers = {}
        if session_cookies:
            headers["Cookie"] = "; ".join(
                f"{k}={v}" for k, v in session_cookies.items()
            )

        base_domain = urlparse(start_url).hostname
        queue = [start_url]

        async with httpx.AsyncClient(
            verify=False, follow_redirects=True,
            timeout=15, headers=headers
        ) as client:
            while queue and len(self.visited) < min(self.max_pages, 50):
                url = queue.pop(0)
                if url in self.visited:
                    continue
                self.visited.add(url)

                try:
                    resp = await client.get(url)
                    body = resp.text
                    results["pages"].append(url)

                    # Extract links
                    for href in re.findall(r'href=["\']([^"\'#?]+)["\']', body):
                        full = urljoin(url, href).split("#")[0]
                        p = urlparse(full)
                        if p.hostname == base_domain and full not in self.visited:
                            queue.append(full)
                            results["endpoints"].append({
                                "url": full, "methods": ["GET"], "params": []
                            })

                    # Extract forms
                    for m in re.finditer(
                        r'<form[^>]*(?:action=["\']([^"\']*)["\'])?'
                        r'[^>]*(?:method=["\']([^"\']*)["\'])?',
                        body, re.IGNORECASE
                    ):
                        action  = m.group(1) or url
                        method  = (m.group(2) or "GET").upper()
                        full_a  = urljoin(url, action).split("?")[0]
                        # Extract inputs nearby
                        inputs  = re.findall(
                            r'<input[^>]*name=["\']([^"\']+)["\']',
                            body[m.start():m.start()+2000]
                        )
                        results["endpoints"].append({
                            "url":     full_a,
                            "methods": [method],
                            "params":  inputs
                        })
                        self.db.add_node(
                            url=full_a, method=[method], params=inputs,
                            node_type=FormatFixer.classify_url(full_a)
                        )

                    # Extract API calls from JS
                    for api_m in re.finditer(
                        r'["\'](/(?:api|v\d+|rest|graphql)[^"\'<>\s]{0,100})["\']',
                        body
                    ):
                        api_url = urljoin(url, api_m.group(1)).split("?")[0]
                        if urlparse(api_url).hostname == base_domain:
                            results["endpoints"].append({
                                "url":     api_url,
                                "methods": ["GET", "POST"],
                                "params":  []
                            })

                    # Extract JS files
                    for js_m in re.finditer(
                        r'src=["\']([^"\']+\.js[^"\']*)["\']', body
                    ):
                        js_url = urljoin(url, js_m.group(1))
                        results["js_files"].append(js_url)

                    await asyncio.sleep(0.1)

                except Exception:
                    pass

    def _url_params(self, url: str) -> List[str]:
        if "?" not in url:
            return []
        query = url.split("?", 1)[1]
        return [p.split("=")[0] for p in query.split("&") if "=" in p]


def _write(path: str, content: str):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content + "\n")
    except Exception:
        pass
