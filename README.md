# 🚀 Space Gesture Control
### FIAP Global Solution 2025 — Space Connect
#### Disciplina: Physical Computing: IoT & IoB

---

## 📋 Índice

1. [Visão Geral do Sistema](#visão-geral-do-sistema)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Gestos e Comandos](#gestos-e-comandos)
4. [Pipeline de Visão Computacional](#pipeline-de-visão-computacional)
5. [Módulos do Código](#módulos-do-código)
   - [AIAudioEngine](#aiaudioengine)
   - [TerrainMap](#terrainmap)
   - [RoverTelemetry](#rovertelemetry)
   - [SyncAI Co-Piloto](#syncai-co-piloto)
   - [MartianScanner](#martianscanner)
   - [GestureDetector](#gesturedetector)
   - [SpaceHUD & TelemetryPanel](#spacehud--telemetrypanel)
6. [API REST (FastAPI)](#api-rest-fastapi)
7. [Funcionalidades Avançadas](#funcionalidades-avançadas)
   - [Autopiloto — Retornar Base](#autopiloto--retornar-base-)
   - [Scanner Geológico](#scanner-geológico-)
   - [Física de Inclinação Dinâmica](#física-de-inclinação-dinâmica)
   - [Desgaste Assimétrico de Pneus](#desgaste-assimétrico-de-pneus)
   - [Relatório de Missão (CSV)](#relatório-de-missão-csv)
   - [Terreno Procedural](#terreno-procedural)
8. [Dependências](#dependências)
9. [Instruções de Execução](#instruções-de-execução)
   - [Pré-requisitos](#pré-requisitos)
   - [Instalação](#instalação)
   - [Controles durante a execução](#controles-durante-a-execução)
10. [Estrutura do Repositório](#estrutura-do-repositório)
11. [Conexão com o Tema Space Connect](#conexão-com-o-tema-space-connect)
12. [Equipe](#equipe)
13. [Demonstração](#demonstração)

---

## 📡 Visão Geral do Sistema

O **Space Gesture Control** é o núcleo de processamento do projeto **ROVER-01** — um sistema de **controle por gestos das mãos** para operação remota de rovers em ambientes espaciais extremos.

Em missões lunares e espaciais, astronautas com trajes pressurizados e luvas espessas não conseguem operar teclados ou interfaces convencionais. Este sistema utiliza **Visão Computacional em tempo real** via webcam para detectar gestos e traduzi-los em comandos de movimento — sem contato físico com equipamentos.

O script Python é responsável por três pilares integrados:

| Pilar | Responsabilidade |
|-------|-----------------|
| **Visão** | Captura e processamento de gestos via MediaPipe |
| **Física** | Cálculo de telemetria, odometria e desgaste de pneus |
| **Comunicação** | Servidor HTTP (FastAPI) que entrega o estado do rover à interface móvel |

O sistema também conta com o **Co-Piloto de IA (SYNC AI)**, que monitora a telemetria e narra eventos críticos por voz, e com um **autopiloto** capaz de retornar o rover à base de forma autônoma.

---

## 🏗️ Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────┐
│                     main.py                             │
│                                                         │
│  ┌──────────────┐   ┌──────────────┐  ┌─────────────┐  │
│  │   Webcam /   │   │  Telemetria  │  │  FastAPI    │  │
│  │  MediaPipe   │──▶│  (Física +   │──▶  REST API   │  │
│  │  (Gestos)    │   │  Terreno)    │  │  :8000      │  │
│  └──────────────┘   └──────────────┘  └─────────────┘  │
│         │                  │                            │
│         ▼                  ▼                            │
│  ┌──────────────┐   ┌──────────────┐                    │
│  │  SYNC AI /   │   │  SpaceHUD +  │                    │
│  │  Voz (TTS)   │   │  Telemetry   │                    │
│  │              │   │  Panel (CV2) │                    │
│  └──────────────┘   └──────────────┘                    │
└─────────────────────────────────────────────────────────┘
         │
         ▼
  App Mobile (consome /telemetry e /scanner)
```

A visão computacional roda em uma **thread dedicada** (`run_vision_loop`), enquanto o **servidor FastAPI** é gerido pelo Uvicorn na thread principal — garantindo que o processamento de imagem não bloqueie a comunicação com a interface móvel.

---

## 🖐️ Gestos e Comandos

| Gesto | Dedos | Comando | Descrição |
|-------|-------|---------|-----------|
| ✊ | Punho fechado (0) | 🚨 EMERGENCIA | Parada total imediata de todos os sistemas |
| ☝️ | 1 dedo | ⬆️ AVANCAR | Movimento frontal do rover |
| ✌️ | 2 dedos | ↺ GIRAR ESQUERDA | Rotação anti-horária |
| 🤟 | 3 dedos | ↻ GIRAR DIREITA | Rotação horária |
| 🖖 | 4 dedos | ⬇️ RECUAR | Movimento reverso |
| ✋ | 5 dedos | ⏹️ PARAR | Parada suave controlada |
| 👍 | Polegar para cima | ⚡ VELOC. MAX | Aumenta multiplicador de velocidade (até 2×) |
| 👎 | Polegar para baixo | 🐢 VELOC. MIN | Reduz multiplicador de velocidade (até 0.2×) |
| 🤙 | Hang Loose | 📡 SCAN AREA | Inicia varredura geológica do terreno |
| 🤘 | Sinal do Rock | 🏠 RETORNAR BASE | Ativa autopiloto de retorno à origem (0, 0) |

A classificação usa lógica prioritária: gestos especiais (Rock, Hang Loose, Polegar) são checados antes da contagem genérica de dedos. Um **buffer de suavização de 8 frames** elimina leituras instáveis.

---

## ⚙️ Pipeline de Visão Computacional

```
Webcam
  │
  ▼
Captura de Frame (OpenCV VideoCapture — 1280×720)
  │
  ▼
Pré-processamento (flip horizontal + BGR → RGB)
  │
  ▼
Inferência MediaPipe Hands
  ├── Detecção de 21 landmarks por mão
  ├── Identificação de lateralidade (direita/esquerda)
  ├── Contagem de dedos levantados
  └── Classificação do gesto
        ├── Rock Sign  (indicador + mindinho)    → RETORNAR BASE
        ├── Hang Loose (polegar + mindinho)      → SCAN AREA
        ├── Polegar sozinho + direção Y          → VELOC. MAX / MIN
        └── Contagem 0–5                         → demais comandos
  │
  ▼
Suavização (buffer de 8 frames — evita flicker)
  │
  ▼
Lógica de Controle
  ├── Autopiloto (RETORNAR BASE) — navega autonomamente até a origem
  ├── Scanner Geológico — detecta anomalias e minerais no terreno
  └── SYNC AI Co-Piloto — monitora telemetria e narra eventos por voz
  │
  ▼
Atualização de Telemetria (RoverTelemetry)
  ├── Física de movimento (velocidade, posição, heading)
  ├── Consumo de bateria por comando
  ├── Temperatura do motor
  ├── Desgaste assimétrico dos 6 pneus (FL/FR/ML/MR/RL/RR)
  └── Elevação e inclinação do terreno
  │
  ▼
Atualização do Estado Global da API (API_TELEMETRY / API_SCANNER)
  │
  ▼
Renderização (OpenCV)
  ├── SpaceHUD (painel esquerdo + comando central + efeito scanner)
  └── TelemetryPanel (painel direito)
        ├── Bateria e Temperatura com barras e alertas piscantes
        ├── Navegação (missão, ODO, X, Y, DIR)
        ├── Velocidade com barra de limite do modo atual
        ├── Radar Topográfico 2D (mapa procedural com rastro)
        └── Diagnóstico de Chassi (rover vista superior + 6 pneus)
  │
  ▼
Exibição em tempo real (cv2.imshow)
```

---

## 🧩 Módulos do Código

### AIAudioEngine
Motor de síntese de voz assíncrono baseado em `pyttsx3`. Utiliza uma fila (`queue.Queue`) e uma thread dedicada para processar narração sem bloquear o loop principal. No Windows, inicializa o `pythoncom` para compatibilidade COM.

### TerrainMap
Gera proceduralmente um mapa lunar de **2000×2000 px** com ruído gaussiano, curvas de nível, crateras e grade. Fornece dados de elevação para a física de inclinação e renderiza o patch do Radar Topográfico 2D com o rastro laranja do rover.

### RoverTelemetry
Núcleo de simulação física. A cada frame calcula:
- **Velocidade** com inércia proporcional ao comando (`dt`-based)
- **Posição** (X, Y) e **heading** por integração de movimento
- **Bateria**: dreno base + dreno por comando + sobrecarga em subidas
- **Temperatura**: interpolação para temperatura-alvo por comando, com ruído
- **Slope**: diferença de elevação a 2 m na direção do heading
- **Odômetro**: acumulado do módulo de distância percorrida

### SyncAI Co-Piloto
Máquina de estados narrativa. Detecta situações críticas (emergência, temperatura > 55°C, bateria < 25%, subida/descida acentuada, scanner ativo) e escolhe frases contextuais aleatórias para narração por voz. Respeita um intervalo mínimo de 9 s entre narrações repetidas do mesmo estado.

### MartianScanner
Ativado pelo gesto **Hang Loose**. Durante a varredura (animação de linha verde percorrendo a tela), gera alvos geológicos proceduralmente com probabilidade de 4% por frame. Ao finalizar, narra um resumo com contagem de achados por tipo. Todos os alvos são persistidos em `all_discovered_targets` para exportação no CSV.

### GestureDetector
Encapsula o `mediapipe.solutions.hands`. O método `count_fingers` avalia cada dedo comparando a posição da ponta com a junta PIP, com lógica especial para o polegar baseada na lateralidade. O método `classify_gesture` aplica prioridade para gestos especiais antes da contagem genérica.

### SpaceHUD & TelemetryPanel
Camadas de renderização OpenCV. O `SpaceHUD` gerencia o painel esquerdo (gestos, histórico, SYNC AI), o indicador central de comando e o efeito de varredura do scanner. O `TelemetryPanel` renderiza o painel direito com barras de bateria/temperatura, navegação, velocidade, radar topográfico e o diagrama de chassi com os 6 pneus coloridos por desgaste.

---

## 🌐 API REST (FastAPI)

O servidor sobe em `http://0.0.0.0:8000` paralelamente ao loop de visão. Os dados são escritos diretamente nas variáveis globais `API_TELEMETRY` e `API_SCANNER` a cada frame, tornando os endpoints sempre atualizados.

### `GET /telemetry`
Retorna o estado completo do rover em JSON:

```json
{
  "battery": 87.3,
  "temperature": 34.1,
  "speed": 2.45,
  "status": "AVANCAR",
  "mission_time": "00:04:12",
  "pos_x": 12.50,
  "pos_y": -3.20,
  "heading": 45.0,
  "slope": 1.20,
  "wheel_wear": [98.1, 97.8, 99.2, 99.0, 97.5, 97.3],
  "odometer": 38.7,
  "signal": 91.4
}
```

### `GET /scanner`
Retorna todos os alvos geológicos detectados na missão:

```json
{
  "targets": [
    {
      "x": 15.32,
      "y": -4.10,
      "time": 1718000000.0,
      "label": "SAFIRA",
      "mission_time": "00:02:30"
    }
  ]
}
```

> O middleware **CORS** (`allow_origins=["*"]`) está habilitado, permitindo acesso irrestrito da aplicação móvel independente da origem.

---

## 🤖 Funcionalidades Avançadas

### Autopiloto — Retornar Base 🤘
- Ativado pelo gesto **Sinal do Rock** e mantido enquanto o gesto for reconhecido
- Calcula continuamente o ângulo para a origem `(0, 0)` via `atan2` e corrige o heading progressivamente
- Ao atingir distância < 1 m da origem, para o rover, narra a conclusão por voz, exibe a tela de **MISSÃO CONCLUÍDA** com fade e encerra o processo via `os._exit(0)`

### Scanner Geológico 📡
- Ativado pelo gesto **Hang Loose**
- Animação de linha verde varrendo a tela de cima a baixo
- Geração procedural de alvos: 14 tipos possíveis (rochas, gelo, minerais preciosos, anomalias)
- Ao finalizar, narra os achados agrupados por tipo com contagem
- Alvos visíveis no Radar Topográfico 2D como marcadores laranja

### Física de Inclinação Dinâmica
- O `slope` é calculado comparando a elevação atual com a elevação a 2 m à frente (na direção do heading)
- **Subidas** (`slope > 0`): aumentam o dreno de bateria e elevam a temperatura-alvo do motor
- **Descidas** (`slope < 0`): reduzem o dreno e permitem resfriamento dos rotores; acrescentam velocidade gravitacional

### Desgaste Assimétrico de Pneus
Cada um dos 6 pneus (FL, FR, ML, MR, RL, RR) possui um **fator de estresse individual**:

| Pneu | Fator | Justificativa |
|------|-------|--------------|
| FL (dianteiro esquerdo) | 1.25 | Maior carga em curvas e aceleração |
| FR (dianteiro direito) | 1.20 | Carga similar ao FL |
| ML (meio esquerdo) | 0.85 | Posição central, menor sobrecarga |
| MR (meio direito) | 0.80 | Posição central, menor sobrecarga |
| RL (traseiro esquerdo) | 1.10 | Tração e frenagem |
| RR (traseiro direito) | 1.05 | Tração e frenagem |

Em curvas, as rodas das extremidades (dianteiras e traseiras) sofrem **1.6×** o estresse das rodas centrais. Ruído randômico de ±10% é aplicado a cada cálculo para simular irregularidades do terreno.

### Relatório de Missão (CSV)
Gerado automaticamente ao encerrar (tecla `Q` ou missão concluída):

- **`MISSION_TELEMETRY_ROVER01.csv`** — tempo de missão, bateria restante, temperatura média e desgaste individual dos 6 pneus
- **`MISSION_SCANNER_ROVER01.csv`** — log completo de achados geológicos com label, coordenadas globais (X, Y) e timestamp de missão

### Terreno Procedural
- Mapa lunar de **2000×2000 px** gerado com `seed=42` (reproduzível)
- Ruído base em baixa resolução expandido com interpolação cúbica e suavizado com Gaussian Blur
- Curvas de nível baseadas em módulo da elevação, 120 crateras aleatórias e grade de referência
- O rover deixa um **rastro laranja** (linha `cv2.line`) no mapa conforme se desloca

---

## 🛠️ Dependências

| Biblioteca | Versão | Uso |
|-----------|--------|-----|
| `opencv-python` | ≥ 4.8.0 | Captura de vídeo, HUD, efeitos visuais, terreno procedural |
| `mediapipe` | 0.10.14 | Detecção de 21 landmarks por mão em tempo real |
| `numpy` | ≥ 1.24.0 | Operações matemáticas, geração de terreno, animações |
| `pyttsx3` | ≥ 2.90 | Motor de voz para narração do Co-Piloto IA |
| `fastapi` | ≥ 0.110.0 | Framework REST para a API de telemetria |
| `uvicorn` | ≥ 0.29.0 | Servidor ASGI para o FastAPI |

---

## 🚀 Instruções de Execução

### Pré-requisitos
- Python 3.11
- Webcam funcional
- Projeto em pasta **sem acentos** no caminho

> ⚠️ **Windows:** evite caminhos como `Área de Trabalho`. Use `C:\GS\` ou `C:\Users\nome\Downloads\GS\`.

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/SEU_USUARIO/space-gesture-control.git
cd space-gesture-control

# 2. Crie um ambiente virtual
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Execute
python main.py
```

Ao iniciar, o sistema abre a janela de visão computacional e sobe o servidor da API simultaneamente:

```
[API] Iniciando servidor FastAPI em http://0.0.0.0:8000
[API] Rotas disponíveis:
      -> http://localhost:8000/telemetry
      -> http://localhost:8000/scanner
```

### Controles durante a execução

| Tecla | Ação |
|-------|------|
| `Q` | Encerra e salva os relatórios de missão (CSV) |
| `S` | Salva screenshot numerado do frame atual |

### Verificar a API

Com o sistema rodando, acesse `http://localhost:8000/telemetry` no navegador ou em qualquer cliente HTTP para ver o JSON de telemetria atualizado em tempo real.

---

## 📁 Estrutura do Repositório

```
space-gesture-control/
├── main.py              # Script principal (visão + física + API)
├── requirements.txt     # Dependências do projeto
└── README.md            # Documentação
```

---

## 🌍 Conexão com o Tema Space Connect

> Resolver problemas fora da Terra para transformar a vida aqui.

A interface gestual desenvolvida para controle espacial tem aplicação direta em **cirurgias remotas**, **controle de equipamentos em ambientes contaminados** e **acessibilidade para pessoas com mobilidade reduzida**.

**ODS Alinhados:** ODS 9 (Inovação e Infraestrutura) | ODS 3 (Saúde e Bem-Estar) | ODS 11 (Cidades e Comunidades Sustentáveis)

---

## 👥 Equipe

| Aluno | RM |
|-------|----|
| Augusto Mendonça | RM 558371 |
| Gabriel Vasquez | RM 557056 |
| Gustavo Oliveira | RM 559163 |

---

## 🎥 Demonstração

> Link do vídeo no YouTube: https://youtu.be/l_VyN70yyNs

---

*FIAP — Global Solution 2025 | Physical Computing: IoT & IoB*
