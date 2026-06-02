# 🚀 Space Gesture Control
### FIAP Global Solution 2025 — Space Connect
#### Disciplina: Physical Computing: IoT & IoB

---

## 📡 Descrição da Solução

Sistema de **controle por gestos das mãos** para operação remota do **ROVER-01** em ambientes espaciais extremos.

Em missões lunares e espaciais, astronautas com trajes pressurizados e luvas espessas não conseguem operar teclados ou interfaces convencionais. Este sistema utiliza **Visão Computacional em tempo real** via webcam para detectar gestos e traduzi-los em comandos de controle do rover — sem qualquer contato físico com equipamentos.

O sistema conta com um **Co-Piloto de IA (SYNC AI)** que monitora a telemetria, narra eventos críticos por voz, e um **sistema de autopiloto** capaz de retornar o rover à base de forma autônoma.

### Conexão com o Tema Space Connect
> Resolver problemas fora da Terra para transformar a vida aqui. A interface gestual desenvolvida para controle espacial tem aplicação direta em cirurgias remotas, controle de equipamentos em ambientes contaminados e acessibilidade para pessoas com mobilidade reduzida.

**ODS Alinhados:** ODS 9 (Inovação e Infraestrutura) | ODS 3 (Saúde e Bem-Estar) | ODS 11 (Cidades e Comunidades Sustentáveis)

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
| 👍 | Polegar para cima | ⚡ VELOC. MAX | Aumenta multiplicador de velocidade |
| 👎 | Polegar para baixo | 🐢 VELOC. MIN | Reduz multiplicador de velocidade |
| 🤙 | Hang Loose | 📡 SCAN AREA | Varredura geológica do terreno |
| 🤘 | Sinal do Rock | 🏠 RETORNAR BASE | Ativa autopiloto de retorno à base |

---

## 🛠️ Bibliotecas Utilizadas

| Biblioteca | Versão | Uso |
|-----------|--------|-----|
| `opencv-python` | ≥ 4.8.0 | Captura de vídeo, HUD, efeitos visuais, terreno procedural |
| `mediapipe` | 0.10.14 | Detecção de 21 landmarks por mão em tempo real |
| `numpy` | ≥ 1.24.0 | Operações matemáticas, geração de terreno, animações |
| `pyttsx3` | ≥ 2.90 | Motor de voz para narração do Co-Piloto IA |

---

## ⚙️ Pipeline de Visão Computacional

```
Webcam
  │
  ▼
Captura de Frame (OpenCV VideoCapture)
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
        ├── Rock Sign  (indicador + mindinho)  → RETORNAR BASE
        ├── Hang Loose (polegar + mindinho)    → SCAN AREA
        ├── Polegar sozinho + direção Y        → VELOC. MAX / MIN
        └── Contagem 0–5                       → demais comandos
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
  ├── Desgaste dos 6 pneus (FL/FR/ML/MR/RL/RR)
  └── Elevação e inclinação do terreno
  │
  ▼
Renderização (OpenCV)
  ├── SpaceHUD (painel esquerdo + comando central + scanner)
  └── TelemetryPanel (painel direito)
        ├── Bateria e Temperatura com barras e alertas piscantes
        ├── Navegação (missão, ODO, X, Y, DIR)
        ├── Velocidade com barra de limite do modo atual
        ├── Radar Topográfico 2D (mapa procedural com rastro)
        └── Diagnóstico de Chassi (rover vista superior + 6 pneus)
  │
  ▼
Exibição em tempo real
```

---

## 🤖 Funcionalidades Avançadas

### SYNC AI Co-Piloto
- Monitora telemetria em tempo real e narra eventos por voz
- Alertas automáticos para emergência, temperatura crítica, bateria baixa, terreno inclinado e autopiloto
- Frases variadas e contextuais para cada situação

### Autopiloto — Retornar Base 🤘
- Detectado pelo gesto **Sinal do Rock**
- Calcula automaticamente a rota de retorno à origem (0,0)
- Ajusta o heading continuamente para apontar à base
- Ao chegar, narra a conclusão, exibe tela de **MISSÃO CONCLUÍDA** e encerra automaticamente

### Scanner Geológico 📡
- Ativado pelo gesto **Hang Loose**
- Detecta anomalias e minerais proceduralmente (rochas, gelo, safiras, rubis, etc.)
- Narra os achados ao final de cada varredura
- Exibe os alvos detectados no Radar Topográfico 2D

### Relatório de Missão (CSV)
Ao encerrar (tecla `Q` ou missão concluída), dois arquivos são gerados automaticamente:
- `MISSION_TELEMETRY_ROVER01.csv` — resumo de telemetria (bateria, temperatura média, desgaste dos pneus)
- `MISSION_SCANNER_ROVER01.csv` — log completo de todos os achados geológicos com coordenadas e timestamp

### Terreno Procedural
- Mapa lunar de 2000×2000px gerado proceduralmente com ruído, crateras, curvas de nível e grade
- O rover deixa um rastro laranja no mapa conforme se move
  
### Física de Inclinação Dinâmica
- O radar calcula o "Slope" (Aclive/Declive) a 2 metros de distância do rover.
- Subidas forçam o motor, consumindo mais bateria e gerando superaquecimento rápido.
- Descidas ativam aceleração gravitacional e permitem o resfriamento dos rotores.
  
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

### Controles durante a execução

| Tecla | Ação |
|-------|------|
| `Q` | Encerra e salva o relatório de missão |
| `S` | Salva screenshot do frame atual |

---

## 📁 Estrutura do Repositório

```
space-gesture-control/
├── main.py              # Código principal
├── requirements.txt     # Dependências
└── README.md            # Documentação
```

---

## 👨‍🚀 Integrantes do Grupo

| Nome | RM |
|------|----|
| Integrante 1 | RM XXXXX |
| Integrante 2 | RM XXXXX |
| Integrante 3 | RM XXXXX |

---

## 🎥 Demonstração

> Link do vídeo no YouTube: [em breve]

---

*FIAP — Global Solution 2025 | Physical Computing: IoT & IoB*
