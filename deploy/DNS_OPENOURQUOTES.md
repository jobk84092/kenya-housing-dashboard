# housing.openourquotes.com → Contabo

Reuse your **Porkbun** domain from the Open Our Quotes app (`www.openourquotes.com` stays on GitHub Pages).

## One DNS record to add

Porkbun → **openourquotes.com** → **DNS Records** → **Add**:

| Type | Host | Answer |
|------|------|--------|
| **A** | **`housing`** | **`13.140.146.55`** |

Do **not** change the apex `@` A records or `www` CNAME (`jobk84092.github.io`) — those keep the quotes site working.

## Verify

```bash
dig +short housing.openourquotes.com A
# → 13.140.146.55

curl -I https://housing.openourquotes.com/_stcore/health
# → HTTP/2 200
```

Caddy on Contabo auto-requests HTTPS once DNS resolves. First cert can take 2–10 minutes after propagation.

## Public URL

**https://housing.openourquotes.com**
