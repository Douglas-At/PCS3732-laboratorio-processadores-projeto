# Matriz de Rastreabilidade — Requisitos × Testes

Cada requisito está associado a pelo menos um caso de teste planejado, com o
respectivo critério de aceite. Na Semana 2, o **RF1** foi executado e passou a
**resultado obtido** (evidência abaixo da tabela); os demais seguem planejados.

| ID | Requisito | Tipo | Caso de teste planejado | Critério de aceite | Status |
|----|-----------|------|-------------------------|--------------------|--------|
| RF1 | Câmera transmite em tempo real | Funcional | Abrir `GET /stream` no central e observar o vídeo | Vídeo contínuo, sem congelar; frames chegam a ≥ 10 fps | **Atendido** ✔ (Sem. 2) |
| RF2 | Botão aciona alarme | Funcional | Pressionar o botão e verificar recebimento do `POST /alert` + notificação no central | Notificação disparada em < 2 s; um único evento por clique (debounce) | Planejado |
| RF3 | Ajuste de qualidade via software | Funcional | Enviar `GET /control?var=quality&val=X` e observar mudança no stream | Qualidade/compressão muda sem reiniciar o firmware | Planejado |
| RNF1 | Controle de latência | Não funcional | Medir tempo de chegada dos frames sob rede normal e degradada | Latência exibida; acima do limiar, qualidade reduz automaticamente | Planejado |
| RNF2 | Disponibilidade ≥ 95% | Não funcional | Derrubar o Wi-Fi por curtos períodos durante operação prolongada | Reconecta automaticamente; disponibilidade medida ≥ 95% | Planejado |
| RNF3 | Código manutenível (baixo acoplamento) | Não funcional | Trocar o backend de câmera (CSI ↔ USB) e o canal de notificação | Troca sem alterar as demais camadas | Planejado |

**Evidência RF1 (Semana 2):** `src/rpi/camera_stream.py` implementado (Flask,
`GET /` + `GET /stream` MJPEG). Executado no Raspberry Pi; o vídeo foi assistido
de outro computador pelo navegador em `http://<pi>:5000/`, com o Pi provendo a
rede em **modo Access Point**. Checagem automatizada do pipe (JPEG válido,
liveness, chunk multipart) em `tests/test_camera_stream.py`.

> **Ponto extra (testes automatizados):** os casos de RF2 (debounce/evento único)
> e RNF3 (backend plugável) são candidatos a testes automatizados, por não
> dependerem de inspeção visual.
