# Multifacturas recorded answers

Recorded from the PAC's test mode (`produccion=NO`) on 2026-11-18 with
`tools/record_multifacturas.py`, using the SAT's public test CSD and a test invoice. The
recorder scrubs every answer: credentials become `USER`/`PASSWORD`, RFCs outside the SAT's
test set (including the PAC's own) become `AAA010101AAA`, and `png` and the
`mensaje_original*` fields are blanked. Synthetic answers are derived from recorded
envelopes for cases test mode cannot produce.

| File | Source |
|------|--------|
| `timbrar33b64_ok.xml` | recorded: a first stamp |
| `timbrar33b64_duplicate.xml` | recorded: the same document again |
| `timbrar33b64_301.xml` | recorded: malformed XML |
| `timbrar33b64_CFDI40102.xml` | recorded: a seal that does not verify |
| `saldo.xml` | recorded: the balance |
| `acuseSAT_200.xml` | recorded: test mode returns 200, not the document |
| `cancelarCfdi_205.xml` | recorded: the SAT does not know test stamps |
| `cancelarCfdi_CACFDI33.xml` | recorded: a CSD password that does not open the key |
| `timbrar33b64_307_cfdi.xml` | synthetic: a duplicate reported as SAT 307 |
| `timbrar33b64_307_uuid.xml` | synthetic: a duplicate reported as SAT 307 |
| `timbrar33b64_307_none.xml` | synthetic: a duplicate reported as SAT 307 |
| `acuseSAT_cfdi.xml` | synthetic: production returns the stamped document |
| `cancelarCfdi_201.xml` | synthetic: SAT 201 |
| `cancelarCfdi_202.xml` | synthetic: SAT 202 |
| `saldo_error.xml` | synthetic: test mode ignores credentials |
