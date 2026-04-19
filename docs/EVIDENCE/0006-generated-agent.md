# Evidência — Bloco 0006: Agente ADK end-to-end

**Status**: estrutura criada; conteúdo preenchido no Bloco 0008 após execução E2E com stack completa.

---

## Execução E2E

> *Preencher no Bloco 0008 com a saída completa do terminal ao rodar:*
> ```
> python -m generated_agent --image docs/fixtures/sample_medical_order.png
> ```

---

## Logs `event=tool.called`

> *Preencher com os registros JSON estruturados mostrando pelo menos 5 entradas `event=tool.called`,
> cada uma com `params_hash`, `duration_ms` e `correlation_id`.*

Exemplo esperado (formato):
```json
{"timestamp": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "extract_exams_from_image", "params_hash": "aabbccdd11223344", "duration_ms": 120.5, "correlation_id": "f47ac10b-..."}
{"timestamp": "...", "level": "INFO", "service": "medical-order-agent", "event": "tool.called", "tool": "search_exam_code", "params_hash": "11223344aabbccdd", "duration_ms": 45.2, "correlation_id": "f47ac10b-..."}
```

---

## POST body capturado

> *Preencher com o corpo da requisição `POST /api/v1/appointments` capturado via log do scheduling-api
> ou sniffer de rede, confirmando `patient_ref=anon-...` e ausência de PII cru.*

Exemplo esperado:
```json
{
  "patient_ref": "anon-a1b2c3d4",
  "exams": [
    {"name": "Hemograma Completo", "code": "HMG-001"},
    {"name": "Glicemia de Jejum", "code": "GLJ-002"},
    {"name": "Colesterol Total", "code": "COL-003"}
  ],
  "scheduled_for": "2026-05-01T09:00:00Z",
  "notes": null
}
```

---

## Tabela final

> *Preencher com o output ASCII exato impresso no terminal ao final da execução.*

Exemplo esperado:
```
+-----+--------------------+---------+
| #   | Exame              | Codigo  |
+-----+--------------------+---------+
| 1   | Hemograma Completo | HMG-001 |
| 2   | Glicemia de Jejum  | GLJ-002 |
| 3   | Colesterol Total   | COL-003 |
+-----+--------------------+---------+
Appointment ID: apt-42  |  Scheduled: 2026-05-01T09:00:00
```
