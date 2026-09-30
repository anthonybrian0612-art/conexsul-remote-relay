# Conexsul Remote Relay V4.1 — Render

Relay WebSocket para intermediar a Central Windows e os coletores Android.

## Publicar no Render

1. Crie um repositório novo no GitHub.
2. Envie os arquivos desta pasta para a raiz do repositório.
3. No Render: New > Web Service.
4. Conecte o repositório.
5. O Render deve detectar o Dockerfile.
6. Selecione o plano Free (se disponível na sua conta).
7. Crie o Web Service.
8. Em Environment, confirme que existe `RELAY_TOKEN`.
   - Se usar `render.yaml`, o Render pode gerar o valor.
   - Copie o valor do token e guarde-o em local seguro.
9. Aguarde o status `Live`.

## Teste

Abra:
`https://SEU-SERVICO.onrender.com/`

Deve retornar JSON parecido com:
`{"ok": true, "service": "Conexsul Remote Relay V4.1", "devices": 0}`

## Endpoint WebSocket

`wss://SEU-SERVICO.onrender.com/ws`

Parâmetros usados pelos clientes:
- `role=collector` ou `role=central`
- `device_id=COLETOR-01`
- `token=SEU_RELAY_TOKEN`

Exemplo conceitual:
`wss://SEU-SERVICO.onrender.com/ws?role=collector&device_id=COLETOR-01&token=...`

Não publique o RELAY_TOKEN em prints, GitHub ou mensagens.
