# system design — o primeiro nível

Do que o Expect Agent é FEITO. O que ele FAZ está no [`design.md`](design.md), e o
call stack — o que chama o quê, e o que emite — ainda não existe: a ordem é essa,
o outline nomeia as peças e o call stack as faz mover.

**A unidade de entrega é uma SKILL, não um CLI.** Ninguém digita `expectagent run`:
quem invoca é o agente hospedeiro, lendo o `SKILL.md` e chamando os scripts. Isso
não é embalagem — apaga duas caixas do desenho, e elas estão em
[o que ser skill apagou](#o-que-ser-skill-apagou).

Cada linha é `<glifo> <Nome>:`, e a indentação é a única sintaxe. Os glifos que
aparecem aqui: 🏢 sistema · ⚙️ script · 🧠 💾 ⚡ camadas · 📦 entidade · 🧩 valor ·
🎯 caso de uso · 🌐 fronteira · 🗄️ repositório · 🗃️ store · 🧵 worker ·
🖥️ interface · ⏱️ scheduler · 🧪 teste. Mais dois **emprestados**, porque a
notação não tem os certos: 🤖 é
*agente* e aqui carrega a skill, 📄 é *template de tela* e aqui carrega documento —
o custo está em [o que a notação não tem](#o-que-a-notação-não-tem-e-custou-aqui).
O vocabulário inteiro em `my meta resources outline_notation`.

```yaml
🏢 ExpectAgent:

  🤖 Skill:
    📄 SKILL.md:
    ⚙️ ask:
    ⚙️ view:
    ⚙️ run:
    ⚙️ judge:
    ⚙️ watch:
    📄 references[]:

  🧠 Domain:
    📦 Case:
    📦 Run:
    📦 AssertContract:
    🧩 Turn:
    🧩 Matcher:
    🧩 ToolSequence:
    🧩 Budget:
    🧩 Score:
    🧩 Verdict:
    🎯 InterviewBehavior:
    🎯 ConfirmExpectation:
    🎯 RunAgainstTarget:
    🎯 ScoreRun:

  🌐 Targets:
    🌐 InProcess:
    🌐 Http:
    🌐 Process:

  💾 Data:
    🗄️ EvalFile:
    🗃️ ConvexStore:

  🖥️ UI:
    🖥️ TauriShell:
    📄 EvalTemplate:
      🧩 CaseWidget:
      🧩 RunViewWidget:
      🧩 RunsWidget:

  ⚡ Background:
    🧵 InngestJobs:
    ⏱️ ProductionSampler:

  🧪 Checks:
    🧪 SchemaContract:
    🧪 NegativeControls:
    🧪 DocTableMatchesSchema:
```

## O que cada camada é

- **`🤖 Skill`** — a unidade de entrega inteira. O `SKILL.md` é o que o agente lê;
  os `⚙️` são os cinco scripts que ele executa, e são a interface toda:
  `ask` entrevista e escreve o caso · `view` monta a tela pra pessoa confirmar ·
  `run` executa contra um alvo e escreve a run de volta · `judge` pontua com
  modelo pinado · `watch` amostra produção. As `references[]` são o que a skill
  ensina por leitura, e não por execução. Instalar é copiar uma pasta.
- **`🧠 Domain`** — o vocabulário, e ele se lê em três blocos. **O que persiste**
  (`📦`): `Case` é um comportamento nomeado, `Run` é uma execução dele,
  `AssertContract` é o JSON Schema — mora aqui porque é a forma do domínio, não
  configuração. **O que é valor** (`🧩`): `Turn` é uma linha do caso, `Matcher`
  afirma sobre um valor, `ToolSequence` afirma sobre a ordem das chamadas,
  `Budget` sobre tempo e custo, `Score` é 0..1 e `Verdict` é o veredito que sai
  dele. **O que acontece** (`🎯`): `InterviewBehavior` transforma desejo em caso,
  `ConfirmExpectation` é o aceite da pessoa, `RunAgainstTarget` executa,
  `ScoreRun` pondera e decide.
- **`🌐 Targets`** — a fronteira do "qualquer agente, qualquer sistema, qualquer
  LLM", e nenhuma das três formas exige que o alvo saiba que existimos:
  `InProcess` é uma função na mesma linguagem, `Http` é um endpoint que o alvo já
  expõe, `Process` é um comando que imprime uma linha de JSON.
- **`💾 Data`** — `EvalFile` é a VERDADE: spec, runs e entrevista no mesmo YAML.
  `ConvexStore` é store e não repositório, e a diferença é o contrato: ele é a cópia
  que deixa a tela rápida e compartilhável, e perder ele não corrompe nada — se
  divergir do arquivo, o arquivo ganha.
- **`🖥️ UI`** — a interface de visualização dos testes, e é o produto: é ela que o
  agente monta e a pessoa confirma. `TauriShell` é o app; dentro, `EvalTemplate` é a
  tela, com `CaseWidget` mostrando o que se pediu, `RunViewWidget` a run aberta e
  `RunsWidget` o histórico.
- **`⚡ Background`** — `InngestJobs` roda o que não pode se perder no meio (uma
  suíte longa, um juiz caro), e `ProductionSampler` amostra produção, onde não
  existe resposta certa.
- **`🧪 Checks`** — teste é inventário do sistema, não anexo. `SchemaContract` prova
  que o contrato é um JSON Schema válido, `NegativeControls` prova o que ele tem
  que RECUSAR, e `DocTableMatchesSchema` impede a tabela do `design.md` de prometer
  primitiva que o contrato não tem. Os negativos estão aqui porque foram eles que
  pegaram o próprio checker passando a vazio.

## A stack, e a linha que ela não atravessa

Tauri + Next.js + Convex + Inngest + HeroUI. É a stack da casa, e é com ela que a
**interface de visualização dos testes** é construída.

E ela cria uma contradição que precisa ficar escrita, porque calada ela mata a
única promessa que o produto tem: *zero infra é a feature*. Um app com backend,
banco e fila é o oposto disso. A linha, então, é esta — e são **dois artefatos**:

- **A skill roda sem nada disso.** Um arquivo e scripts. Sem conta, sem servidor,
  sem Convex. É ela que vai pro open source, e é dela que a promessa fala.
- **O app é produto nosso, em cima.** Quem quer a tela bonita, o histórico
  compartilhado e a suíte longa rodando sozinha instala o app. Quem não quer, tem o
  arquivo e o terminal — e não perde nenhuma asserção por isso.

O teste que decide se a linha foi respeitada: **desligue o Convex e o Inngest, e a
skill continua dando o mesmo veredito.** Se não continuar, o app virou dependência
e a promessa morreu.

## O que ser skill APAGOU

- **A camada `⌨️ CLI` inteira.** Os quatro verbos digitáveis — `ask`, `view`, `run`,
  `watch` — viraram scripts dentro da skill; o quinto, `judge`, era agente e virou
  script junto. Verbo digitado por humano era superfície a manter, documentar e
  versionar que ninguém tinha pedido.
- **O agente `🤖 Interviewer`.** A gente não entrega entrevistador: entrega a
  instrução que faz QUALQUER agente entrevistar. Isso é mais forte do que era o
  desenho anterior — funciona no Claude Code, no Cursor, em quem vier.
- **A pergunta "que pacote?"** — pypi e npm deixam de ser o canal. A medição de
  nome continua valendo (o `.com` e o GitHub seguem importando), mas o registro de
  pacote virou detalhe.

**O `⚙️ judge` continua script, e é decisão, não sobra.** Ele não pode ser o agente
hospedeiro julgando a si mesmo: o contrato exige modelo e versão pinados, e o
hospedeiro é justamente o que a gente não controla.

## As linhas sem filho, e o que elas confessam

As folhas da árvore param aqui porque este é o primeiro nível — descer antes de o
nome estar acordado é gastar o desenho inventando nome. Mas três param por outro
motivo: a decisão **não foi tomada**.

- **`⚙️ watch`** e **`⏱️ ProductionSampler`** — produção está declarada no
  `design.md` e nunca foi desenhada. Taxa de amostragem, o que se guarda, e quem
  paga o juiz: nada tem resposta.
- **`📄 references[]`** — o que a skill ensina por documento e o que ela resolve por
  script ainda não está cortado.
- **`🧩 Turn`** — o domínio ainda não distingue turno de assert-sobre-a-sequência, e
  o schema já distingue.

## O que a notação não tem, e custou aqui

O `outline_notation` está declarado como *drafted*, e pede que o primeiro projeto
que abrir com ele anote o custo. Anotando: **faltam dois glifos.**

- **Skill.** Usei `🤖`, que é agente. Uma skill não é um agente — é o que um agente
  carrega. `🔹 skills[]: Skill` já existe no template como TIPO, mas não há glifo
  para quando a skill é a própria unidade de entrega.
- **Documento.** Usei `📄`, que é *template de tela*, para `SKILL.md` e para as
  references. Num sistema que é feito de documentos, isso força o glifo errado.

## References

- [`design.md`](design.md) — o que o sistema FAZ, com o contrato de asserts
- [`expectagent.schema.json`](expectagent.schema.json) — `AssertContract` em disco
- `my meta resources outline_notation` — quando se alcança um outline, e por quê
- `my meta resources callstack_notation` — a outra notação, para quando as peças
  já tiverem nome
