# SAT status answers

Recorded from the SAT's ConsultaCFDIService on 2026-11-18 with
`tools/record_sat_consulta.py`. The one call uses the SAT's test RFCs and a test UUID
and needs no credentials, so there is nothing to scrub. Synthetic answers are derived
from the recorded envelope for the states a test UUID cannot produce.

| File | Source |
|------|--------|
| `consulta_no_encontrado.xml` | recorded: the SAT does not know the test UUID |
| `consulta_vigente_sin_aceptacion.xml` | synthetic: Vigente / Cancelable sin aceptación / (empty) |
| `consulta_vigente_con_aceptacion.xml` | synthetic: Vigente / Cancelable con aceptación / (empty) |
| `consulta_vigente_no_cancelable.xml` | synthetic: Vigente / No cancelable / (empty) |
| `consulta_vigente_en_proceso.xml` | synthetic: Vigente / Cancelable con aceptación / En proceso |
| `consulta_vigente_rechazada.xml` | synthetic: Vigente / Cancelable con aceptación / Solicitud rechazada |
| `consulta_cancelado_sin_aceptacion.xml` | synthetic: Cancelado / Cancelable sin aceptación / Cancelado sin aceptación |
| `consulta_cancelado_con_aceptacion.xml` | synthetic: Cancelado / Cancelable con aceptación / Cancelado con aceptación |
| `consulta_cancelado_plazo_vencido.xml` | synthetic: Cancelado / Cancelable con aceptación / Plazo vencido |
| `consulta_cancelado_sin_estatus.xml` | synthetic: Cancelado / Cancelable sin aceptación / (empty) |
| `consulta_codigo_n.xml` | synthetic: Vigente / Cancelable sin aceptación / (empty) |
| `consulta_estado_desconocido.xml` | synthetic: Suspendido / Cancelable sin aceptación / (empty) |
| `consulta_cancelable_desconocido.xml` | synthetic: Vigente / Cancelable / (empty) |
| `consulta_estatus_desconocido.xml` | synthetic: Vigente / Cancelable con aceptación / Desconocido |
