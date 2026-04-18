# PII — Detecção e Anonimização (Microsoft Presidio)

## 1. Por que Presidio
Framework open-source da Microsoft para detecção, redação, mascaramento e anonimização de PII em texto, imagens e dados estruturados. Combina NER (spaCy/transformers), regex e lógica customizada. Python 3.10–3.13.

## 2. Componentes
- **presidio-analyzer** — detecta entidades PII (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, IP_ADDRESS, LOCATION, DATE_TIME, etc.).
- **presidio-anonymizer** — transforma o texto: `replace`, `redact`, `mask`, `hash`, `encrypt`.
- **presidio-image-redactor** — redige PII em imagens (usa OCR + analyzer).

## 3. Instalação
```bash
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg
# Português:
python -m spacy download pt_core_news_lg
```

## 4. Uso mínimo
```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

text = "João Silva, CPF 123.456.789-00, tel (11) 98888-7777"
results = analyzer.analyze(text=text, language="pt")
anon = anonymizer.anonymize(text=text, analyzer_results=results)
print(anon.text)
```

## 5. Reconhecedores customizados (relevante para PT-BR)
CPF, CNPJ, RG e telefones brasileiros não estão no set default — precisam de recognizers custom:
```python
from presidio_analyzer import PatternRecognizer, Pattern

cpf_pattern = Pattern(name="cpf", regex=r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", score=0.9)
cpf_recognizer = PatternRecognizer(
    supported_entity="BR_CPF",
    patterns=[cpf_pattern],
    supported_language="pt",
)
analyzer.registry.add_recognizer(cpf_recognizer)
```

## 6. Estratégias de anonimização
| Operador | Resultado |
|---|---|
| `replace` | `<PERSON>` |
| `redact` | `` (remove) |
| `mask` | `Jo****` |
| `hash` | determinístico, útil para joins |
| `encrypt` | reversível com chave |

## 7. Integração no pipeline do desafio
Posição crítica: **entre o OCR e o envio para o LLM**.
```
imagem → OCR → texto bruto → [Presidio PII Guardrail] → texto mascarado → LLM
```
Entidades a mascarar: `PERSON`, `BR_CPF`, `BR_CNPJ`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `LOCATION`, `DATE_TIME` (nascimento). **NÃO mascarar** nomes de exames, códigos de procedimento ou termos médicos genéricos.

Recomendação: implementar como **serviço interno** (módulo `pii_guard/`) chamado pelo servidor MCP de OCR antes de retornar a resposta, E também como `before_model_callback` no agente ADK como dupla camada de defesa.

## 8. Boas práticas
- Configurar `language="pt"` e modelo spaCy compatível.
- Tunar `score_threshold` por entidade (padrão 0.35 é baixo).
- Manter lista `allow_list` para termos de domínio (ex.: "Hemograma").
- Registrar auditoria (hash da entrada + tipo de entidade detectada + operação aplicada), nunca o valor bruto.
- Testes unitários com casos reais sintéticos brasileiros.

## 9. Fontes
- `https://microsoft.github.io/presidio/`
- `https://github.com/microsoft/presidio`
- `https://microsoft.github.io/presidio/samples/python/customizing_presidio_analyzer/`
