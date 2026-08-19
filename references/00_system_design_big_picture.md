# big picture — quem faz o quê, e onde você entra

```mermaid
flowchart LR
    P(("👤 você"))
    A(("🤖 seu agente<br/>de código"))
    APP[["🖥️ o app<br/>te mostra pra você validar"]]
    R(("🎯 seu agente<br/>no ar"))
    C(("🙋 seu cliente"))

    P -->|"diz o que quer"| A
    A -->|"monta a tela"| APP
    P -->|"valida, ou ajusta uma linha"| APP
    A -->|"constrói"| R
    APP ==>|"confere, toda vez"| R
    R -->|"atende"| C
    APP -.->|"quebrou? te avisa antes do cliente"| P

    style APP fill:#1e3a8a,stroke:#60a5fa,stroke-width:4px,color:#fff
```

Duas pessoas, dois agentes, e **um app no meio de tudo**. Ele te mostra o que o
agente vai fazer *antes* de ele fazer, você valida ali, e depois ele fica
conferindo — é por isso que a notícia ruim chega em você antes de chegar no
cliente.

Como isso funciona por dentro está em [`system_design.md`](system_design.md); o
contrato de asserts, com as 40 primitivas e a origem de cada uma, está em
[`design.md`](design.md).
