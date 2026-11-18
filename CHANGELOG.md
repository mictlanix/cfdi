# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial project setup.
- The import package is `mictlanix.cfdi` and the distribution `mictlanix-cfdi`.
- CFDI 4.0 documents of every type (I, E, P, N, T) as typed models with the SAT's exact names,
  with derived totals and tax summaries, `payment_comprobante` for payment documents, and
  `to_xml`.
- Validation against the SAT's XSDs and the Anexo 20 rules that can be decided offline; every
  violation names its node, attribute and rule.
- Original strings with the SAT's stylesheets, and sealing with the issuer's CSD.
- Reading of sealed and stamped documents, their TimbreFiscalDigital 1.1, its original string
  and the data for the SAT verification QR.
- Complements at the versions the SAT accepts: Pagos 2.0, Nómina 1.2, Carta Porte 3.1,
  Comercio Exterior 2.0, Impuestos Locales 1.0, Divisas 1.0, Donatarias 1.1, Leyendas Fiscales
  1.0, INE 1.1, Aerolíneas 1.0, Detallista 1.3.1, Turista Pasajero Extranjero 1.0, Estado de
  Cuenta de Combustibles 1.2, Consumo de Combustibles 1.1, Gastos de Hidrocarburos 1.0, Ingresos
  de Hidrocarburos 1.0, Notarios Públicos 1.0, Obras de Arte y Antigüedades 1.0, Pago en Especie
  1.0, Vales de Despensa 1.0, Vehículo Usado 1.0, Renovación y Sustitución de Vehículos 1.0,
  Certificado de Destrucción 1.0, Servicios Parciales de Construcción 1.0, CFDI Registro Fiscal
  1.0, PFIC 1.0, Instituciones Educativas Privadas 1.0, Venta de Vehículos 1.1 and Hidrocarburos
  y Petrolíferos 1.0.
- `mictlanix.cfdi.pac`: one asynchronous PAC interface, `PacClient` (stamp, find a stamp,
  request a cancellation), with immutable values (`Stamp`, `CancellationRequest`,
  `CsdCredentials`) and typed errors (`PacRejected`, `PacUnavailable`, `PacTimeout`, under
  `PacError`). Cancellation requests are validated on
  construction (reason 01 requires the substitute UUID, 02–04 forbid it).
- `SimulatedPac`, an offline PAC for development and tests: every stamping and cancellation
  outcome configurable per document or UUID, the recipient's answers, and state in a
  caller-supplied store (`SimulatorStore`, `InMemoryStore` by default) that several processes
  can share.
- `MultifacturasPac`, the PAC client for Facturación México (Multifacturas), configured with
  `MultifacturasSettings`: stamping (`timbrar33b64`, a duplicate returns the existing stamp),
  cancellation (`cancelacion2022`; the SAT's code gives pending or accepted), and `balance()`. HTTPS with certificate verification only;
  nothing is read from the environment. Offline tests replay scrubbed recordings of the PAC's
  test mode; live tests are opt-in through `MULTIFACTURAS_USER` and `MULTIFACTURAS_PASSWORD`.
- Constitution v1.1.0: a timeout may also be resolved by resubmitting the same sealed document
  to a PAC that answers a resubmission with the existing stamp.
- `mictlanix.cfdi.sat`: the SAT's status of any CFDI from its public status service
  (ConsultaCFDIService), independent of the PAC and without credentials. `SatStatusClient` with
  its values (`SatStatus`, `SatState`, `Cancellability`, `CancellationStatus`) and errors
  (`SatRejected`, `SatUnavailable`, `SatTimeout`, under `SatError`); `SatConsultaClient`
  configured with `SatConsultaSettings`; `SimulatedSatStatusClient`, which answers from a
  `SimulatedPac`'s state. Offline tests replay a recorded answer and synthetic ones; a live test
  is opt-in through `SAT_CONSULTA_LIVE=1`.
- Constitution v1.1.1 and v1.1.2: the SAT status surface (its protocol, values, enums, errors and
  every SAT status client) is exported from `mictlanix.cfdi.sat`, and only from there.

### Changed

- The fixed Mexico City offset moved to a shared private module, used by sealing and by the
  simulated PAC's clock; no behaviour change.
- The HTTPS transport of the PAC clients moved to a shared private module, used by the PAC and
  the SAT clients; no behaviour change.

### Not emitted

- Carta Porte 2.0 and 3.0, Comercio Exterior 1.1, Pagos 1.0, Estado de Cuenta de Combustibles
  1.1 and Terceros, which the SAT has retired. They are read as raw XML and never emitted.
