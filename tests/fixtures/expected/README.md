# Expected results

Every file here is written by hand from the SAT's published rules, never taken from the
library's output, so the tests compare the library against an independent result.

- `ingreso.xml`: the invoice of quickstart.md scenario 1 as XML, with its totals and with
  format-valid placeholders for the seal attributes (`NoCertificado` is twenty zeros).
- `ingreso.cadena.txt`: its original string, written in the order the SAT's
  `cadenaoriginal_4_0.xslt` emits the values: `||`, each value separated by `|`, then `||`.
  It has no trailing newline.

## Known seals

For three documents sealed with the SAT's public test CSD (`tests/fixtures/csd/`), the original
string was written by hand in the SAT's stylesheet order (`cadenaoriginal_4_0.xslt`, and
`Pagos20.xslt` for the complement), and the seal was produced from it with the OpenSSL command
line, not with the library:

| Document | Original string | Seal |
|----------|-----------------|------|
| The quickstart invoice (type I), sealed: as `ingreso.cadena.txt` with `NoCertificado` 30001000000500003416 | `ingreso.sellado.cadena.txt` | `ingreso.sello.txt` |
| A credit note (type E) for 50.00 plus IVA, `TipoRelacion` 01 to UUID 5FB2822E-396D-4725-8521-CDC4BDD20CCF, `UsoCFDI` G02 | `egreso.cadena.txt` | `egreso.sello.txt` |
| A payment (type P) built by `payment_comprobante`, `UsoCFDI` CP01, settling 116.00 of one MXN invoice with IVA at 16% | `pago.cadena.txt` | `pago.sello.txt` |

Commands (OpenSSL 4.0.3), run in this folder:

```sh
for name in ingreso.sellado egreso pago; do
  openssl dgst -sha256 -sign \
    <(openssl pkcs8 -inform DER -in ../csd/eku9003173c9.key -passin pass:<published password>) \
    "$name.cadena.txt" | openssl base64 -A > "${name%.sellado}.sello.txt"
done
```

Each seal is RSA PKCS#1 v1.5 over the UTF-8 bytes of the original string with SHA-256, in
Base64. RSA PKCS#1 v1.5 signatures are deterministic, so the library must reproduce these exactly.
