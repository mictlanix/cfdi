# Validation rules: CFDI 4.0 (Anexo 20)

**Source**: the SAT's CFDI 4.0 error matrix,
`http://omawww.sat.gob.mx/tramitesyservicios/Paginas/documentos/MatrizDeErrores_CFDI_v40_20260325.xls`,
linked on `http://omawww.sat.gob.mx/tramitesyservicios/Paginas/anexo_20.htm`. Published 2026-03-24
(server `Last-Modified`); retrieved 2026-11-18. The limits of CFDI40167, CFDI40180, CFDI40186 and
CFDI40198, and the NumeroPedimento rules of CFDI40194 and CFDI40199, are taken from the Anexo 20
standard (`documentos/Anexo20_2022.pdf` on the same page).

**Status**: `implemented in US1` or `implemented in US2` means the library reports a violation of the
rule with its code as `Violation.rule`; `out of scope` gives the reason. Rules marked
`enforced by the XSD` are still checked: the XSD reports them with its own rule name. Codes are
copied exactly as the SAT publishes them, including the `CFDI1402xx` series.

| Code | Element | Attribute | Rule | Status |
|------|---------|-----------|------|--------|
| CFDI40101 | Comprobante | Fecha | Fecha matches the pattern and is the local time of issue | out of scope: pattern enforced by the XSD and reported with its XSD rule name; the local time of issue needs the stamping time and the time zone of the place of issue |
| CFDI40102 | Comprobante | Sello | Sello verifies against the original string | out of scope: verifying a received seal; the library writes the seal itself (FR-015) |
| CFDI40103 | Comprobante | FormaPago | FormaPago absent for types T, N and P | implemented in US1 |
| CFDI40104 | Comprobante | FormaPago | FormaPago in c_FormaPago | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40105 | Comprobante | FormaPago | FormaPago is 99 when MetodoPago is PPD | implemented in US1 |
| CFDI40106 | Comprobante | Certificado | Certificado is a valid certificate | out of scope: enforced when the CSD is loaded (CsdError) |
| CFDI40107 | Comprobante | SubTotal | SubTotal has at most the currency's decimals | implemented in US1 |
| CFDI40108 | Comprobante | SubTotal | For I, E and N, SubTotal equals the rounded sum of the concept amounts | implemented in US1 |
| CFDI40109 | Comprobante | SubTotal | For T and P, SubTotal is zero | implemented in US1 |
| CFDI40110 | Comprobante | Descuento | Descuento is not greater than SubTotal | implemented in US1 |
| CFDI40111 | Comprobante | Descuento | Descuento exists, equal to the rounded sum of concept discounts, exactly when a concept has one (I, E, N) | implemented in US1 |
| CFDI40112 | Comprobante | Descuento | Descuento has at most the currency's decimals | implemented in US1 |
| CFDI40113 | Comprobante | Moneda | Moneda in c_Moneda | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40114 | Comprobante | TipoCambio | With MXN, TipoCambio is absent or 1 | implemented in US1 |
| CFDI40115 | Comprobante | TipoCambio | TipoCambio present when Moneda is neither MXN nor XXX | implemented in US1 |
| CFDI40116 | Comprobante | TipoCambio | TipoCambio absent when Moneda is XXX | implemented in US1 |
| CFDI40117 | Comprobante | TipoCambio | TipoCambio matches its pattern | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40118 | Comprobante | TipoCambio | TipoCambio within the currency's tolerance, else Confirmacion | out of scope: needs the published exchange rate of the day and a PAC confirmation key |
| CFDI40119 | Comprobante | Total | Total equals SubTotal - Descuento + transferred - withheld taxes | implemented in US1; local taxes added in US2 |
| CFDI40120 | Comprobante | Total | Total above the limit needs Confirmacion | out of scope: the limit is set by the Resolución Miscelánea Fiscal and needs a PAC confirmation key |
| CFDI40121 | Comprobante | TipoDeComprobante | TipoDeComprobante in c_TipoDeComprobante | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40122 | Comprobante | Exportacion | Exportacion 02 requires the Comercio Exterior complement | implemented in US2 |
| CFDI40123 | Comprobante | Exportacion | Exportacion in c_Exportacion | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40124 | Comprobante | MetodoPago | MetodoPago in c_MetodoPago | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40125 | Comprobante | MetodoPago | MetodoPago absent for T and P | implemented in US1 |
| CFDI40126 | Comprobante | LugarExpedicion | LugarExpedicion in c_CodigoPostal | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40127 | Comprobante | Confirmacion | Confirmacion absent when within limits | out of scope: depends on the limits of CFDI40118 and CFDI40120 |
| CFDI40128 | Comprobante | Confirmacion | Confirmacion was requested from the PAC | out of scope: decided by the PAC at stamping |
| CFDI40129 | Comprobante | Confirmacion | Confirmacion used only once | out of scope: decided by the PAC at stamping |
| CFDI40130 | cfdi:InformacionGlobal | - | InformacionGlobal present for type I to XAXX010101000 named PUBLICO EN GENERAL | implemented in US1 |
| CFDI40131 | cfdi:InformacionGlobal | Periodicidad | Periodicidad in c_Periodicidad | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40132 | cfdi:InformacionGlobal | Periodicidad | Periodicidad 05 requires Emisor RegimenFiscal 621 | implemented in US1 |
| CFDI40133 | cfdi:InformacionGlobal | Meses | Meses in c_Meses | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40134 | cfdi:InformacionGlobal | Meses | Meses 01 to 12 unless Periodicidad is 05 | implemented in US1 |
| CFDI40135 | cfdi:InformacionGlobal | Meses | Meses 13 to 18 when Periodicidad is 05 | implemented in US1 |
| CFDI40136 | cfdi:InformacionGlobal | Año | Año is the current year or up to five years before | out of scope: needs the stamping time |
| CFDI40137 | cfdi:CfdiRelacionados | TipoRelacion | TipoRelacion in c_TipoRelacion | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40138 | cfdi:Emisor | Nombre | Emisor Nombre in the list of registered RFCs | out of scope: needs the SAT's live registries |
| CFDI40139 | cfdi:Emisor | Nombre | Emisor Nombre belongs to its Rfc | out of scope: needs the SAT's live registries |
| CFDI40140 | cfdi:Emisor | RegimenFiscal | Emisor RegimenFiscal in c_RegimenFiscal | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40141 | cfdi:Emisor | RegimenFiscal | Emisor RegimenFiscal fits the persona type of its Rfc (12 characters moral, 13 física) | implemented in US1 |
| CFDI40142 | cfdi:Emisor | FacAtrAdquirente | FacAtrAdquirente is a valid operation number | out of scope: needs the SAT's RFC validation service |
| CFDI40143 | cfdi:Receptor | Rfc | Receptor Rfc in the list of registered RFCs | out of scope: needs the SAT's live registries |
| CFDI40144 | cfdi:Receptor | Nombre | Receptor Nombre in the list of registered RFCs | out of scope: needs the SAT's live registries |
| CFDI40145 | cfdi:Receptor | Nombre | Receptor Nombre belongs to its Rfc | out of scope: needs the SAT's live registries |
| CFDI40146 | cfdi:Receptor | Nombre | Receptor named PUBLICO EN GENERAL has Rfc XAXX010101000 | implemented in US1 |
| CFDI40147 | cfdi:Receptor | DomicilioFiscalReceptor | DomicilioFiscalReceptor in the list of registered RFCs | out of scope: needs the SAT's live registries |
| CFDI40148 | cfdi:Receptor | DomicilioFiscalReceptor | DomicilioFiscalReceptor belongs to the Receptor Rfc | out of scope: needs the SAT's live registries |
| CFDI40149 | cfdi:Receptor | DomicilioFiscalReceptor | With a generic Rfc, DomicilioFiscalReceptor equals LugarExpedicion | implemented in US1 |
| CFDI40150 | cfdi:Receptor | ResidenciaFiscal | ResidenciaFiscal in c_Pais | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40151 | cfdi:Receptor | ResidenciaFiscal | ResidenciaFiscal absent unless the Rfc is XEXX010101000 | implemented in US1 |
| CFDI40152 | cfdi:Receptor | ResidenciaFiscal | ResidenciaFiscal is not MEX | implemented in US1 |
| CFDI40153 | cfdi:Receptor | ResidenciaFiscal | ResidenciaFiscal present for XEXX010101000 with Comercio Exterior or NumRegIdTrib | implemented in US2 |
| CFDI40154 | cfdi:Receptor | NumRegIdTrib | NumRegIdTrib absent unless the Rfc is XEXX010101000 | implemented in US1 |
| CFDI40155 | cfdi:Receptor | NumRegIdTrib | NumRegIdTrib present for XEXX010101000 with Comercio Exterior | implemented in US2 |
| CFDI40156 | cfdi:Receptor | NumRegIdTrib | NumRegIdTrib matches the format c_Pais gives for ResidenciaFiscal | implemented in US1 for countries with a published format; countries verified online need the SAT's live registries |
| CFDI40157 | cfdi:Receptor | RegimenFiscalReceptor | RegimenFiscalReceptor in c_RegimenFiscal | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40158 | cfdi:Receptor | RegimenFiscalReceptor | RegimenFiscalReceptor fits the persona type of the Receptor Rfc | implemented in US1 |
| CFDI40159 | cfdi:Receptor | RegimenFiscalReceptor | With a generic Rfc, RegimenFiscalReceptor is 616 | implemented in US1 |
| CFDI40160 | cfdi:Receptor | UsoCFDI | UsoCFDI in c_UsoCFDI | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40161 | cfdi:Receptor | UsoCFDI | UsoCFDI applies to the persona type and RegimenFiscalReceptor per c_UsoCFDI | implemented in US1 |
| CFDI40162 | cfdi:Conceptos/Concepto | ClaveProdServ | Concepto ClaveProdServ in c_ClaveProdServ | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40163 | cfdi:Conceptos/Concepto | ClaveProdServ | Complements c_ClaveProdServ requires are present | out of scope: the current c_ClaveProdServ requires no complement for any key, so the rule cannot fail; CFDI140228 covers the one published requirement |
| CFDI40164 | cfdi:Conceptos/Concepto | ClaveProdServ | Taxes c_ClaveProdServ requires are present | implemented in US1 |
| CFDI40165 | cfdi:Conceptos/Concepto | ClaveUnidad | ClaveUnidad in c_ClaveUnidad | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40166 | cfdi:Conceptos/Concepto | ValorUnitario | For I, E and N, Concepto ValorUnitario is greater than zero | implemented in US1 |
| CFDI40167 | cfdi:Conceptos/Concepto | Importe | Concepto Importe within the limits from Cantidad and ValorUnitario | implemented in US1 |
| CFDI40168 | cfdi:Conceptos/Concepto | Descuento | Concepto Descuento has at most the decimals of its Importe | implemented in US1 |
| CFDI40169 | cfdi:Conceptos/Concepto | Descuento | Concepto Descuento is not greater than its Importe | implemented in US1 |
| CFDI40170 | cfdi:Conceptos/Concepto | ObjetoImp | ObjetoImp in c_ObjetoImp | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40171 | cfdi:Conceptos/Concepto | ObjetoImp | ObjetoImp 02 requires the concept Impuestos node | implemented in US1 |
| CFDI40172 | cfdi:Conceptos/Concepto | ObjetoImp | ObjetoImp 01, 03, 04 or 05 forbids the concept Impuestos node | implemented in US1 |
| CFDI40173 | cfdi:Conceptos/Concepto:Impuestos | Impuestos | A concept Impuestos node holds transferred or withheld taxes | implemented in US1 |
| CFDI40174 | cfdi:Conceptos/Concepto:Impuestos:Traslados/Traslado | Base | Concept Traslado Base greater than zero | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40175 | cfdi:Conceptos/Concepto:Impuestos:Traslados/Traslado | Impuesto | Concept Traslado Impuesto in c_Impuesto | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40176 | cfdi:Conceptos/Concepto:Impuestos:Traslados/Traslado | TipoFactor | Concept Traslado TipoFactor in c_TipoFactor | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40177 | cfdi:Conceptos/Concepto:Impuestos:Traslados/Traslado | TipoFactor | Concept Traslado Exento has no TasaOCuota or Importe | implemented in US1 |
| CFDI40178 | cfdi:Conceptos/Concepto:Impuestos:Traslados/Traslado | TipoFactor | Concept Traslado Tasa or Cuota has TasaOCuota and Importe | implemented in US1 |
| CFDI40179 | cfdi:Conceptos/Concepto:Impuestos:Traslados/Traslado | TasaOCuota | Concept Traslado TasaOCuota in c_TasaOCuota for its tax and factor | implemented in US1 |
| CFDI40180 | cfdi:Conceptos/Concepto:Impuestos:Traslados/Traslado | Importe | Concept Traslado Importe within the limits from Base and TasaOCuota | implemented in US1 |
| CFDI40181 | cfdi:Conceptos/Concepto:Impuestos:Retenciones/Retencion | Base | Concept Retencion Base greater than zero | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40182 | cfdi:Conceptos/Concepto:Impuestos:Retenciones/Retencion | Impuesto | Concept Retencion Impuesto in c_Impuesto | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40183 | cfdi:Conceptos/Concepto:Impuestos:Retenciones/Retencion | TipoFactor | Concept Retencion TipoFactor in c_TipoFactor | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40184 | cfdi:Conceptos/Concepto:Impuestos:Retenciones/Retencion | TipoFactor | Concept Retencion TipoFactor is not Exento | implemented in US1 |
| CFDI40185 | cfdi:Conceptos/Concepto:Impuestos:Retenciones/Retencion | TasaOCuota | Concept Retencion TasaOCuota in c_TasaOCuota for its tax and factor | implemented in US1 |
| CFDI40186 | cfdi:Conceptos/Concepto:Impuestos:Retenciones/Retencion | Importe | Concept Retencion Importe within the limits from Base and TasaOCuota | implemented in US1 |
| CFDI40187 | cfdi:Conceptos/Concepto:ACuentaTerceros | RfcACuentaTerceros | RfcACuentaTerceros in the l_LCO list | out of scope: needs the SAT's live registries |
| CFDI40188 | cfdi:Conceptos/Concepto:ACuentaTerceros | RfcACuentaTerceros | RfcACuentaTerceros differs from the Emisor and Receptor Rfc | implemented in US1 |
| CFDI40189 | cfdi:Conceptos/Concepto:ACuentaTerceros | NombreACuentaTerceros | NombreACuentaTerceros is registered, or the fixed description for EXT990101NI1 | implemented in US1 for RfcACuentaTerceros EXT990101NI1; other RFCs need the SAT's live registries |
| CFDI40190 | cfdi:Conceptos/Concepto:ACuentaTerceros | NombreACuentaTerceros | NombreACuentaTerceros belongs to RfcACuentaTerceros | out of scope: needs the SAT's live registries |
| CFDI40191 | cfdi:Conceptos/Concepto:ACuentaTerceros | RegimenFiscalACuentaTerceros | RegimenFiscalACuentaTerceros in c_RegimenFiscal | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40192 | cfdi:Conceptos/Concepto:ACuentaTerceros | DomicilioFiscalACuentaTerceros | DomicilioFiscalACuentaTerceros in the list of registered RFCs | out of scope: needs the SAT's live registries |
| CFDI40193 | cfdi:Conceptos/Concepto:ACuentaTerceros | DomicilioFiscalACuentaTerceros | DomicilioFiscalACuentaTerceros belongs to the RFC, or equals LugarExpedicion for EXT990101NI1 | implemented in US1 for RfcACuentaTerceros EXT990101NI1; other RFCs need the SAT's live registries |
| CFDI40194 | cfdi:Conceptos/Concepto:InformacionAduanera | NumeroPedimento | Concepto InformacionAduanera NumeroPedimento follows the Anexo 20 rules | implemented in US1 for the customs office, broker licence and consecutive number; the year bound needs the stamping time |
| CFDI40195 | cfdi:Conceptos/Concepto:InformacionAduanera | NumeroPedimento | Concepto NumeroPedimento absent with Comercio Exterior | implemented in US2 |
| CFDI40196 | cfdi:Conceptos/Concepto:Parte | ClaveProdServ | Parte ClaveProdServ in c_ClaveProdServ | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40197 | cfdi:Conceptos/Concepto:Parte | ValorUnitario | Parte ValorUnitario greater than zero | implemented in US1 |
| CFDI40198 | cfdi:Conceptos/Concepto:Parte | Importe | Parte Importe within the limits from Cantidad and ValorUnitario | implemented in US1 |
| CFDI40199 | cfdi:Conceptos/Concepto:Parte:InformacionAduanera | NumeroPedimento | Parte InformacionAduanera NumeroPedimento follows the Anexo 20 rules | implemented in US1 for the customs office, broker licence and consecutive number; the year bound needs the stamping time |
| CFDI40200 | cfdi:Conceptos/Concepto:Parte:InformacionAduanera | NumeroPedimento | Parte NumeroPedimento absent with Comercio Exterior | implemented in US2 |
| CFDI40201 | cfdi:Impuestos | Impuestos | Document Impuestos absent for T and P | implemented in US1 |
| CFDI40202 | cfdi:Impuestos | TotalImpuestosRetenidos | TotalImpuestosRetenidos has at most the currency's decimals | implemented in US1 |
| CFDI40203 | cfdi:Impuestos | TotalImpuestosRetenidos | TotalImpuestosRetenidos equals the sum of the Retencion amounts | implemented in US1 |
| CFDI40204 | cfdi:Impuestos | TotalImpuestosTrasladados | TotalImpuestosTrasladados has at most the currency's decimals | implemented in US1 |
| CFDI40205 | cfdi:Impuestos | TotalImpuestosTrasladados | TotalImpuestosTrasladados equals the sum of the Traslado amounts | implemented in US1 |
| CFDI40206 | cfdi:Impuestos:Retenciones | Retenciones | Retenciones requires TotalImpuestosRetenidos | implemented in US1 |
| CFDI40207 | cfdi:Impuestos:Retenciones/Retencion | Impuesto | Document Retencion Impuesto in c_Impuesto | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40208 | cfdi:Impuestos:Retenciones/Retencion | Impuesto | One document Retencion per tax | implemented in US1 |
| CFDI40209 | cfdi:Impuestos:Retenciones/Retencion | Importe | A Retencion amount requires TotalImpuestosRetenidos | implemented in US1 |
| CFDI40210 | cfdi:Impuestos:Retenciones/Retencion | Importe | Document Retencion Importe has at most the currency's decimals | implemented in US1 |
| CFDI40211 | cfdi:Impuestos:Retenciones/Retencion | Importe | Document Retencion Importe equals the rounded sum of concept withholdings of that tax | implemented in US1 |
| CFDI40212 | cfdi:Impuestos:Traslados | Traslados | TotalImpuestosTrasladados present when a concept has a factor other than Exento | implemented in US1 |
| CFDI40213 | cfdi:Impuestos:Traslados/Traslado | Traslado | With only Exento concepts, document Traslado has only Base, Impuesto and TipoFactor | implemented in US1 |
| CFDI40214 | cfdi:Impuestos:Traslados/Traslado | Base | Document Traslado Base has at most the currency's decimals | implemented in US1 |
| CFDI40215 | cfdi:Impuestos:Traslados/Traslado | Base | Document Traslado Base equals the rounded sum of concept bases with that tax and rate | implemented in US1 |
| CFDI40216 | cfdi:Impuestos:Traslados/Traslado | Base | With only Exento concepts, document Traslado Base equals the rounded sum of concept bases | implemented in US1 |
| CFDI40217 | cfdi:Impuestos:Traslados/Traslado | Impuesto | Document Traslado Impuesto in c_Impuesto | out of scope: enforced by the XSD and reported with its XSD rule name |
| CFDI40218 | cfdi:Impuestos:Traslados/Traslado | Impuesto | One document Traslado per tax, factor and rate | implemented in US1 |
| CFDI40219 | cfdi:Impuestos:Traslados/Traslado | TasaOCuota | Document Traslado TasaOCuota in c_TasaOCuota for its tax and factor | implemented in US1 |
| CFDI40220 | cfdi:Impuestos:Traslados/Traslado | Importe | Document Traslado Importe has at most the currency's decimals | implemented in US1 |
| CFDI40221 | cfdi:Impuestos:Traslados/Traslado | Importe | Document Traslado Importe equals the rounded sum of concept amounts with that tax and rate | implemented in US1 |
| CFDI40222 | Comprobante | Exportacion | Exportacion 01 or 03 forbids the Comercio Exterior complement | implemented in US2 |
| CFDI140223 | cfdi:Conceptos/Concepto:ACuentaTerceros | RegimenFiscalACuentaTerceros | RegimenFiscalACuentaTerceros is 616 for EXT990101NI1 | implemented in US1 |
| CFDI140224 | cfdi:Conceptos/Concepto:Impuestos:Retenciones/Retencion | Impuesto | Withholdings for issuers marked for retention (régimen 626) | out of scope: needs the SAT's live registries |
| CFDI140225 | cfdi:Conceptos/Concepto:Impuestos:Retenciones/Retencion | Impuesto | Withholdings for issuers marked for retention (régimen 626) | out of scope: needs the SAT's live registries |
| CFDI140226 | cfdi:Conceptos/Concepto | ObjetoImp | ObjetoImp 06 or 08 forbids concept IVA and IEPS taxes | implemented in US1 |
| CFDI140227 | cfdi:Conceptos/Concepto | ObjetoImp | ObjetoImp 07 forbids concept IVA and requires a transferred IEPS | implemented in US1 |
| CFDI140228 | cfdi:Conceptos/Concepto | ClaveProdServ | Keys 15101505, 15101514 and 15101515 on I or E need the Hidrocarburos y Petrolíferos complement | implemented in US1 |
| CFDI40999 | Error no clasificado | No clasificado | Unclassified error | out of scope: not a rule (unclassified error) |

**Totals**: 72 implemented in US1, 6 implemented in US2, 51 out of scope.
**Fixed values of a payment document (type P)**: this matrix covers five of them (CFDI40103,
CFDI40109, CFDI40116, CFDI40125, CFDI40201). The other three, `Moneda` `XXX`, `Total` `0` and the
single fixed concept, are rules of the Pagos 2.0 matrix, which this feature does not implement
(complement matrices are out of scope apart from the Pagos 2.0 derivations). They are guaranteed by
construction instead: `payment_comprobante` always sets them.

## Document types per complement (`complement-document-type`)

Each complement's allowed document types come from its published standard (the "Estándar" document
on `https://www.sat.gob.mx/portal/public/tramites/complementos-de-factura`), read on 2026-11-18. A
complement whose standard states no restriction has no entry and is accepted on any type.

| Complement | Allowed types | Source |
|------------|---------------|--------|
| Pagos 2.0 | P | Standard (payment documents) |
| Nómina 1.2 | N | Standard (payroll documents) |
| Carta Porte 3.1 | I, T | Standard |
| Comercio Exterior 2.0 | I, T | Standard |
| Estado de Cuenta de Combustibles 1.2 | I | Standard rev. B: `tipoDeComprobante` "es requerido y debe ser {ingreso}" |
| Hidrocarburos y Petrolíferos 1.0 | I, E | Standard rev. B: "Si este atributo tiene el valor P, T o N este complemento concepto no debe existir" |
| Aerolíneas 1.0, CFDI Registro Fiscal 1.0, Certificado de Destrucción 1.0, Consumo de Combustibles 1.1, Detallista 1.3.1, Divisas 1.0, Donatarias 1.1, INE 1.1, Instituciones Educativas Privadas 1.0, Leyendas Fiscales 1.0, Notarios Públicos 1.0, Obras de Arte y Antigüedades 1.0, Pago en Especie 1.0, PFIC 1.0, Renovación y Sustitución de Vehículos 1.0, Servicios Parciales de Construcción 1.0, Turista Pasajero Extranjero 1.0, Vales de Despensa 1.0, Vehículo Usado 1.0, Venta de Vehículos 1.1 | any | Their standards state no document-type restriction |
| Impuestos Locales 1.0 | any | No restriction (User Story 2) |
| Gastos de Hidrocarburos 1.0, Ingresos de Hidrocarburos 1.0 | any (unverified) | Not published on the SAT's complements page on 2026-11-18, so their standards could not be read; no entry |
