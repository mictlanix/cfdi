"""Nómina 1.2 on a payroll document (type N)."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from mictlanix.cfdi import Comprobante, Concepto, Receptor, nomina12, validate

D = Decimal
MakeInvoice = Callable[..., Comprobante]
Check = Callable[[Comprobante], str]
NOMINA = '/cfdi:Comprobante/cfdi:Complemento/nomina12:Nomina'


def nomina(**receptor: str) -> nomina12.Nomina:
    values = {
        'Curp': 'CACX760510MGTSHC04',
        'NumSeguridadSocial': '12345678901',
        'FechaInicioRelLaboral': date(2020, 1, 6),
        'Antigüedad': 'P358W',
        'TipoContrato': '01',
        'TipoRegimen': '02',
        'NumEmpleado': '120',
        'PeriodicidadPago': '04',
        'SalarioDiarioIntegrado': D('350.00'),
        'ClaveEntFed': 'HID',
    }
    values.update(receptor)
    return nomina12.Nomina(
        TipoNomina='O',
        FechaPago=date(2026, 11, 15),
        FechaInicialPago=date(2026, 11, 1),
        FechaFinalPago=date(2026, 11, 15),
        NumDiasPagados=D('15'),
        TotalPercepciones=D('5000.00'),
        TotalDeducciones=D('500.00'),
        Emisor=nomina12.Emisor(RegistroPatronal='B5510768108'),
        Receptor=nomina12.Receptor(**values),  # type: ignore[arg-type]
        Percepciones=nomina12.Percepciones(
            TotalSueldos=D('5000.00'),
            TotalGravado=D('5000.00'),
            TotalExento=D('0.00'),
            Percepcion=[
                nomina12.Percepcion(
                    TipoPercepcion='001',
                    Clave='001',
                    Concepto='Sueldo',
                    ImporteGravado=D('5000.00'),
                    ImporteExento=D('0.00'),
                )
            ],
        ),
        Deducciones=nomina12.Deducciones(
            TotalImpuestosRetenidos=D('500.00'),
            Deduccion=[
                nomina12.Deduccion(
                    TipoDeduccion='002', Clave='002', Concepto='ISR', Importe=D('500.00')
                )
            ],
        ),
    )


def payroll(
    make_invoice: MakeInvoice, complemento: nomina12.Nomina, tipo: str = 'N'
) -> Comprobante:
    return make_invoice(
        totals=False,
        TipoDeComprobante=tipo,
        FormaPago=None,
        Receptor=Receptor(
            Rfc='CACX7605101P8',
            Nombre='XOCHILT CASAS CHAVEZ',
            DomicilioFiscalReceptor='36257',
            RegimenFiscalReceptor='605',
            UsoCFDI='CN01',
        ),
        Conceptos=[
            Concepto(
                ClaveProdServ='84111505',
                Cantidad=D('1'),
                ClaveUnidad='ACT',
                Descripcion='Pago de nómina',
                ValorUnitario=D('5000.00'),
                Importe=D('5000.00'),
                Descuento=D('500.00'),
                ObjetoImp='01',
            )
        ],
        Complemento=[complemento],
    )


def test_a_payroll_document(make_invoice: MakeInvoice, builds_validates_seals: Check) -> None:
    cadena = builds_validates_seals(payroll(make_invoice, nomina()))
    assert '|5000.00|500.00|MXN|4500.00|N|' in cadena
    assert '|1.2|O|2026-11-15|2026-11-01|2026-11-15|15|5000.00|500.00|' in cadena


def test_invalid_payroll_data_names_the_complement_node(make_invoice: MakeInvoice) -> None:
    found = {
        (v.node, v.attribute) for v in validate(payroll(make_invoice, nomina(TipoContrato='ZZ')))
    }
    assert (f'{NOMINA}/nomina12:Receptor', 'TipoContrato') in found


def test_nomina_is_allowed_only_on_payroll_documents(make_invoice: MakeInvoice) -> None:
    document = payroll(make_invoice, nomina(), tipo='I')
    found = [v.node for v in validate(document) if v.rule == 'complement-document-type']
    assert found == [NOMINA]
