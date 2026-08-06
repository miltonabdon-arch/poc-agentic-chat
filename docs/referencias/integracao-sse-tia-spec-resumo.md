# Integração de Canal via Contrato SSE/TIA — Spec (resumo)

> Resumo extraído de `.specs/features/integracao-sse-tia/spec.md` do
> repositório do projeto principal. Contém apenas o que
> `docs/ARQUITETURA.md` desta PoC referencia diretamente — ver
> `docs/referencias/README.md`.

## O que é, no projeto real

O Agente POV atende clientes por voz via URA, além do canal de mensageria
digital em texto. O agente **não implementa** a URA, telefonia, SIP/MRCP ou
STT/TTS — ele recebe a interação de voz já resolvida em texto pelo
componente **TIA** da TIM, consumida exclusivamente através de um contrato
de eventos Server-Sent Events (SSE) padrão: `GET`/`POST /agent/sse`.

## ⚠️ Nota de integridade da fonte (importante)

O Escopo Técnico v1.2 (documento que rege o projeto principal) cita
repetidamente um **"Adendo A"** que detalharia esse protocolo SSE em
profundidade — mas esse adendo está **ausente** do texto recebido pelo
projeto principal. Ou seja: **o contrato SSE/TIA real ainda não está
totalmente especificado**, nem para o projeto principal, nem
(consequentemente) para esta PoC.

## Por que isso importa para esta PoC

`docs/ARQUITETURA.md` desta PoC descreve o Channel Gateway como "mock do
contrato de entrada/saída (mock do formato SSE/TIA)" — isso não é apenas
uma simplificação de escopo da PoC, é reflexo direto de o contrato real
ainda não existir por completo no projeto principal. Não há um contrato
SSE/TIA formal para esta PoC replicar com fidelidade, mesmo que quisesse.

**Implicação prática:** o Channel Gateway desta PoC simula a forma do
contrato (`Interaction` normalizada), não o protocolo SSE real — quando o
"Adendo A" for obtido pelo projeto principal, o adaptador real precisará ser
revisado, e esta PoC não deve ser tratada como validação desse contrato
específico.
