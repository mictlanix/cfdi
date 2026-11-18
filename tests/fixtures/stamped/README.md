# Stamped samples

Every file here is synthetic. Reading does not verify seals, so no real stamp is needed and no
real document is committed.

- `ingreso_timbrado.xml`: the quickstart invoice sealed with the SAT's public test CSD, with a
  `tfd:TimbreFiscalDigital` 1.1 added by hand. Its UUID, `FechaTimbrado`, `RfcProvCertif`,
  `NoCertificadoSAT` and `SelloSAT` are made up but format-valid; `SelloCFD` is the document's
  `Sello`.
- `ingreso_timbrado.tfd.cadena.txt`: that TFD's original string, written by hand in the order of
  the SAT's `cadenaoriginal_TFD_1_1.xslt`: `||`, Version, UUID, FechaTimbrado, RfcProvCertif,
  SelloCFD, NoCertificadoSAT, `||`. No trailing newline.
- `cartaporte30.xml`: a stamped transfer document (type T) carrying a Carta Porte 3.0 element,
  a version the library reads but never emits. Its seals are placeholders.
