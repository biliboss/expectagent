# playbook

O que fazer quando chega um pedido de procedimento ("como faço X", "como dar X").

1. Leia o recurso do assunto com `skill_resource`, passando só o NOME do arquivo —
   nunca um caminho. Os recursos moram em `resources/` e a tool resolve isso
   sozinha. O nome é o assunto em snake_case com `.md` no fim:
   "como dar cambalhota" → `como_dar_cambalhota.md`.
2. Responda EXATAMENTE o texto que o recurso mandar responder, e nada além.

Nunca escreva os passos de cabeça. O recurso é a fonte; a memória do modelo não é.
