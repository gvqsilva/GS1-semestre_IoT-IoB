"""
╔══════════════════════════════════════════════════════════════╗
║         SPACE GESTURE CONTROL — GS Physical Computing        ║
║         Controle por Gestos para Operação Espacial Remota    ║
╚══════════════════════════════════════════════════════════════╝

Gestos mapeados:
    ✊ Punho fechado   → EMERGENCIA       (parada total imediata)
    ☝️  1 dedo         → AVANCAR          (movimento frontal)
    ✌️  2 dedos        → GIRAR ESQUERDA   (rotação anti-horária)
    🤟 3 dedos        → GIRAR DIREITA    (rotação horária)
    🖖 4 dedos        → RECUAR           (movimento reverso)
    ✋ 5 dedos        → PARAR            (parada suave)
    👍 Polegar cima   → VELOC. MAX       (velocidade máxima)
    👎 Polegar baixo  → VELOC. MIN       (velocidade mínima)
    🤙 Hang Loose     → SCAN AREA        (varredura geológica)
    🤘 Sinal do Rock  → RETORNAR BASE    (Ativa o Autopiloto)
"""

import os
import sys
import warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore')

import cv2
import mediapipe as mp
import numpy as np
import time
import math
import textwrap
import csv
import threading
import queue
import pyttsx3
from collections import deque, Counter

# ── IMPORTAÇÕES DA API REST ──
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ──────────────────────────────────────────────
#  ESTADO GLOBAL DA API (PONTE PYTHON <-> APP)
# ──────────────────────────────────────────────
API_TELEMETRY = {
    "battery": 100.0,
    "temperature": 22.0,
    "speed": 0.0,
    "status": "AGUARDANDO...",
    "mission_time": "00:00:00",
    "pos_x": 0.0,
    "pos_y": 0.0,
    "heading": 0.0,
    "slope": 0.0,
    "wheel_wear": [100.0] * 6,
    "odometer": 0.0,
    "signal": 100.0
}
API_SCANNER = []

app = FastAPI(title="Rover API")

# Permite que o App mobile acesse a API sem bloqueios
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/telemetry")
def get_telemetry():
    return API_TELEMETRY

@app.get("/scanner")
def get_scanner():
    return {"targets": API_SCANNER}

# ──────────────────────────────────────────────
#  CONFIGURAÇÕES VISUAIS
# ──────────────────────────────────────────────
COLORS = {
    "bg_panel":     (10, 10, 20),
    "orange":       (0, 140, 255),
    "cyan":         (255, 220, 0),
    "green":        (0, 255, 120),
    "red":          (0, 60, 255),
    "white":        (240, 240, 240),
    "gray":         (100, 100, 120),
    "yellow":       (0, 220, 255),
    "panel_border": (0, 100, 200),
}

COMMAND_COLORS = {
    "PARAR":          (0, 200, 255),
    "AVANCAR":        (0, 255, 120),
    "GIRAR ESQUERDA": (255, 200, 0),
    "GIRAR DIREITA":  (255, 140, 0),
    "VELOC. MAX":     (0, 255, 200),
    "VELOC. MIN":     (100, 180, 255),
    "RECUAR":         (0, 165, 255),
    "SCAN AREA":      (0, 255, 80),
    "RETORNAR BASE":  (255, 50, 255),
    "EMERGENCIA":     (0, 0, 255),
    "AGUARDANDO...":  (100, 100, 120),
}


# ──────────────────────────────────────────────
#  MOTOR DE VOZ DA IA
# ──────────────────────────────────────────────
class AIAudioEngine:
    def __init__(self):
        self.q = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            text = self.q.get()
            if text is None: break

            def run_tts():
                if os.name == 'nt':
                    try:
                        import pythoncom
                        pythoncom.CoInitialize()
                    except ImportError:
                        pass
                try:
                    engine = pyttsx3.init()
                    engine.setProperty('rate', 215)
                    engine.say(text)
                    engine.runAndWait()
                except Exception as e:
                    print(f"\n[ERRO DE AUDIO]: {e}")

                if os.name == 'nt':
                    try:
                        pythoncom.CoUninitialize()
                    except: pass

            t = threading.Thread(target=run_tts)
            t.start()
            t.join()
            self.q.task_done()

    def speak(self, text):
        clean_text = text.replace("[", "").replace("]", "").replace("CRITICO", "Crítico").replace("ALERTA", "Alerta")
        self.q.put(clean_text)


# ──────────────────────────────────────────────
#  GERADOR DE TERRENO PROCEDURAL
# ──────────────────────────────────────────────
class TerrainMap:
    def __init__(self, size=2000, scale=4.0):
        self.size, self.scale = size, scale
        self.map_img = np.full((size, size, 3), (12, 15, 20), dtype=np.uint8)

        np.random.seed(42)
        base_noise = np.random.rand(size//25, size//25) * 150.0
        noise_resized = cv2.resize(base_noise, (size, size), interpolation=cv2.INTER_CUBIC)
        self.elevation_data = cv2.GaussianBlur(noise_resized, (61, 61), 0)

        contours = np.zeros_like(self.elevation_data, dtype=np.uint8)
        contours[(self.elevation_data % 8) < 0.6] = 255
        self.map_img[contours == 255] = (30, 45, 60)

        for _ in range(120):
            cx, cy, r = np.random.randint(0, size), np.random.randint(0, size), np.random.randint(10, 60)
            cv2.circle(self.map_img, (cx, cy), r, (8, 10, 15), -1)
            cv2.circle(self.map_img, (cx, cy), r, (50, 65, 80), 2)

        for i in range(0, size, 100):
            cv2.line(self.map_img, (i, 0), (i, size), (25, 30, 40), 1)
            cv2.line(self.map_img, (0, i), (size, i), (25, 30, 40), 1)

        self.last_x, self.last_y = size//2, size//2

    def get_elevation(self, pos_x, pos_y):
        px = max(0, min(self.size-1, int(self.size//2 + pos_x * self.scale)))
        py = max(0, min(self.size-1, int(self.size//2 - pos_y * self.scale)))
        return self.elevation_data[py, px]

    def get_patch_and_update(self, pos_x, pos_y, rx, ry):
        px, py = int(self.size//2 + pos_x * self.scale), int(self.size//2 - pos_y * self.scale)
        cv2.line(self.map_img, (self.last_x, self.last_y), (px, py), (0, 140, 255), 2)
        self.last_x, self.last_y = px, py
        px_s, py_s = max(rx, min(self.size - rx, px)), max(ry, min(self.size - ry, py))
        return self.map_img[py_s-ry:py_s+ry, px_s-rx:px_s+rx]


# ──────────────────────────────────────────────
#  TELEMETRIA
# ──────────────────────────────────────────────
class RoverTelemetry:
    def __init__(self):
        self.mission_start = time.time()
        self.battery, self.temperature, self.speed, self.speed_target = 100.0, 22.0, 0.0, 0.0
        self.speed_mult, self.signal = 1.0, 98.0
        self.pos_x, self.pos_y, self.heading, self.odometer = 0.0, 0.0, 0.0, 0.0
        self.elevation, self.slope = 0.0, 0.0
        self.arrived_home = False

        self.speed_history, self.temp_history = deque(maxlen=40), deque(maxlen=40)
        self._last_update = time.time()

        self.temp_sum = 0.0
        self.temp_count = 0

    def update(self, command, terrain):
        now, dt = time.time(), min(time.time() - self._last_update, 0.1)
        self._last_update = now

        self.elevation = terrain.get_elevation(self.pos_x, self.pos_y)
        rad_look = math.radians(self.heading)
        self.slope = terrain.get_elevation(self.pos_x + math.cos(rad_look)*2.0, self.pos_y + math.sin(rad_look)*2.0) - self.elevation

        if command == "VELOC. MAX": self.speed_mult = min(self.speed_mult + 0.5 * dt, 2.0)
        elif command == "VELOC. MIN": self.speed_mult = max(self.speed_mult - 0.5 * dt, 0.2)

        base_speeds = {"AVANCAR": 5.0, "RECUAR": -3.5, "GIRAR ESQUERDA": 1.0, "GIRAR DIREITA": 1.0, "RETORNAR BASE": 5.0}
        base = base_speeds.get(command, 0.0)

        # ── FÍSICA DO AUTOPILOTO ──
        if command == "RETORNAR BASE":
            target_angle = math.degrees(math.atan2(-self.pos_y, -self.pos_x))
            diff = (target_angle - self.heading + 180) % 360 - 180
            self.heading += np.sign(diff) * min(abs(diff), 40.0 * dt)

            dist_to_home = math.hypot(self.pos_x, self.pos_y)
            if dist_to_home < 1.0:
                base = 0.0
                self.arrived_home = True

        if command in ("AVANCAR", "VELOC. MAX", "VELOC. MIN", "RECUAR", "RETORNAR BASE"):
            target = base * self.speed_mult
            target += self.slope * 0.15 if command == "RECUAR" else -self.slope * 0.20
            if command != "RECUAR" and base > 0 and target < 0.5: target = 0.5
            self.speed_target = target
        else: self.speed_target = base

        self.speed += (self.speed_target - self.speed) * min(dt * (6.0 if command == "EMERGENCIA" else 3.0), 1.0)
        if abs(self.speed) < 0.03: self.speed = 0.0

        dist_frame = self.speed * dt
        self.odometer += abs(dist_frame)
        self.pos_x += dist_frame * math.cos(math.radians(self.heading))
        self.pos_y += dist_frame * math.sin(math.radians(self.heading))

        if command == "GIRAR ESQUERDA": self.heading = (self.heading - 40.0 * dt) % 360
        elif command == "GIRAR DIREITA": self.heading = (self.heading + 40.0 * dt) % 360

        drain = 0.030 * dt + {"AVANCAR": 0.120, "SCAN AREA": 0.800, "VELOC. MAX": 0.200, "RETORNAR BASE": 0.150}.get(command, 0.0) * dt
        if self.slope > 0 and abs(self.speed) > 0.1: drain += (self.slope * 0.05) * dt
        self.battery = max(0.0, self.battery - drain)

        target_temp = {"AVANCAR": 48.0, "VELOC. MAX": 52.0, "RETORNAR BASE": 50.0, "EMERGENCIA": 68.0}.get(command, 22.0)
        if abs(self.speed) > 0.1: target_temp += self.slope * 2.5
        self.temperature += (target_temp - self.temperature) * min(dt * 0.4, 1.0) + np.random.uniform(-0.05, 0.05)
        self.signal = max(60.0, min(100.0, 85.0 + 13.0 * abs(math.sin(now * 0.3)) + np.random.uniform(-1.0, 1.0)))

        self.speed_history.append(abs(self.speed))
        self.temp_history.append(self.temperature)

        self.temp_sum += self.temperature
        self.temp_count += 1

    @property
    def mission_time(self):
        elapsed = int(time.time() - self.mission_start)
        return f"{elapsed//3600:02d}:{(elapsed%3600)//60:02d}:{elapsed%60:02d}"
    @property
    def battery_color(self): return COLORS["green"] if self.battery > 60 else COLORS["yellow"] if self.battery > 25 else COLORS["red"]
    @property
    def temp_color(self): return COLORS["green"] if self.temperature < 40 else COLORS["yellow"] if self.temperature < 55 else COLORS["red"]
    @property
    def speed_mode_label(self): return "MAX" if self.speed_mult >= 1.5 else "MIN" if self.speed_mult <= 0.5 else "NOR"
    @property
    def speed_mode_color(self): return (0, 255, 200) if self.speed_mult >= 1.5 else (100, 180, 255) if self.speed_mult <= 0.5 else COLORS["white"]


# ──────────────────────────────────────────────
#  CO-PILOTO SYNC (INTELIGÊNCIA NARRATIVA)
# ──────────────────────────────────────────────
class SyncAI:
    def __init__(self, audio_engine):
        self.last_msg = "SISTEMA ONLINE. AVALIANDO TOPOGRAFIA."
        self.last_voice_time = time.time()
        self.current_state = "NORMAL"
        self.audio = audio_engine
        self.audio.speak("Sistemas inicializados. Controle de gestos calibrado e pronto.")

    def update(self, t, command, is_scanning):
        now = time.time()
        msg = "MONITORANDO TELEMETRIA E RELEVO..."
        new_state = "NORMAL"
        phrases = []

        if command == "EMERGENCIA":
            new_state = "EMERGENCIA"
            msg = "[CRITICO] PARADA DE EMERGENCIA ACIONADA!"
            phrases = ["Emêrgencia acionada! Cortando energia dos motores.", "Aviso crítico! Freio de emergência travado."]
        elif command == "RETORNAR BASE":
            new_state = "RETORNAR_BASE"
            msg = "[AUTOPILOTO] ROTA DE RETORNO. ASSUMINDO CONTROLE."
            phrases = ["Autopiloto engajado. Calculando rota segura de retorno.", "Navegacao autonoma ativada. Voltando para casa."]
        elif t.temperature > 55:
            new_state = "TEMP_CRITICA"
            msg = "[ALERTA] SOBREAQUECIMENTO DO MOTOR. REDUZA VELOCIDADE!"
            phrases = ["Alerta vermelho! Temperatura do núcleo em nivel crítico.", "Risco de derretimento do motor. Pare o veículo agora."]
        elif t.slope > 2.0 and command in ["AVANCAR", "VELOC. MAX"]:
            new_state = "SUBIDA_FORTE"
            msg = "[TERRENO] ACLIVE INGREME DETECTADO. CONSUMO EXTRA."
        elif t.slope < -2.0 and abs(t.speed) > 4.0:
            new_state = "DESCIDA_FORTE"
            msg = "[TERRENO] DECLIVE ACENTUADO. ATIVANDO FREIO MOTOR."
        elif t.battery < 25:
            new_state = "BATERIA_BAIXA"
            msg = "[ALERTA] BATERIA CRITICA. INICIE PROTOCOLO DE RETORNO."
            phrases = ["Nivel de bateria crítico. O retorno e altamente recomendado."]
        elif is_scanning:
            new_state = "SCANNING"
            msg = "[ANALISE] INICIANDO VARREDURA GEOLOGICA NO SETOR."

        if new_state != "NORMAL":
            if new_state != self.current_state or (now - self.last_voice_time > 9.0):
                self.current_state = new_state
                self.last_voice_time = now
                if phrases:
                    self.audio.speak(np.random.choice(phrases))
        else:
            self.current_state = "NORMAL"

        self.last_msg = msg
        return msg


# ──────────────────────────────────────────────
#  SCANNER ESPACIAL E RELATÓRIO
# ──────────────────────────────────────────────
class MartianScanner:
    def __init__(self):
        self.active, self.scan_y, self.targets = False, 0, []
        self.found_this_scan = []
        self.all_discovered_targets = []
        self.labels = ["ROCHA BASALTICA", "ANOMALIA MAGNETICA", "GELO SUBTERRANEO", "CRATERA", "ENXOFRE PURO", "SAFIRA", "RUBI", "CARBONATO DE FERRO (SIDERITA)", "MANCHAS DE LEOPARDO", "ROVER QUEBRADO", "LIXO ESPACIAL", "VESTIGIOS DE FERRO", "VESTIGIOS DE MANGANES", "VESTIGIOS DE ZINCO"]
        self.audio_engine = None

    def start(self, height, audio_engine):
        if not self.active:
            self.active, self.scan_y = True, 0
            self.targets, self.found_this_scan = [], []
            self.audio_engine = audio_engine
            self.audio_engine.speak(np.random.choice([
                "Iniciando varredura geologica no perimetro.",
                "Acionando radar de terreno e busca por minerais."
            ]))

    def update(self, telemetry, height):
        if not self.active: return
        self.scan_y += 6

        if np.random.rand() < 0.04 and len(self.targets) < 5:
            ox, oy = np.random.uniform(-40, 40), np.random.uniform(-40, 40)
            label = np.random.choice(self.labels)
            target_data = {"x": telemetry.pos_x + ox, "y": telemetry.pos_y + oy, "time": time.time(), "label": label, "mission_time": telemetry.mission_time}

            self.targets.append(target_data)
            self.found_this_scan.append(label)
            self.all_discovered_targets.append(target_data)

        if self.scan_y >= height:
            self.active = False
            scan_atual = [t["label"] for t in self.targets]
            if not scan_atual:
                self.audio_engine.speak("Varredura concluida. Nenhuma anomalia geologica detectada.")
            else:
                counts = Counter(scan_atual)
                resumo = "Varredura concluída. Detectamos no terreno: "
                itens = []
                for k, v in counts.items():
                    if v == 1:
                        itens.append(f"uma {k.lower()}" if k in ["ROCHA BASALTICA", "ANOMALIA MAGNETICA", "CRATERA","ENXOFRE PURO", "SAFIRA", "RUBI", "CARBONATO DE FERRO (SIDERITA)", "MANCHAS DE LEOPARDO", "ROVER QUEBRADO", "LIXO ESPACIAL", "VESTIGIOS DE FERRO", "VESTIGIOS DE MANGANES", "VESTIGIOS DE ZINCO" ] else f"um {k.lower()}")
                    else:
                        itens.append(f"{v} ocorrencias de {k.lower()}")
                resumo += " e ".join(itens) + "."
                self.audio_engine.speak(resumo)


# ──────────────────────────────────────────────
#  UI: GESTOS & PAINÉIS
# ──────────────────────────────────────────────
class GestureDetector:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands    = self.mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.75, min_tracking_confidence=0.6)
        self.FINGER_TIPS, self.FINGER_PIP = [4, 8, 12, 16, 20], [3, 6, 10, 14, 18]

    def process(self, frame_rgb): return self.hands.process(frame_rgb)

    def count_fingers(self, hand_landmarks, handedness):
        lm, fingers = hand_landmarks.landmark, []
        fingers.append(1 if (lm[4].x < lm[3].x if handedness == "Right" else lm[4].x > lm[3].x) else 0)
        for tip, pip in zip(self.FINGER_TIPS[1:], self.FINGER_PIP[1:]): fingers.append(1 if lm[tip].y < lm[pip].y else 0)
        return sum(fingers), fingers

    def classify_gesture(self, total_fingers, fingers, hand_landmarks):
        if fingers[1] == 1 and fingers[2] == 0 and fingers[3] == 0 and fingers[4] == 1: return "RETORNAR BASE"
        if fingers[0] == 1 and fingers[4] == 1 and sum(fingers[1:4]) == 0: return "SCAN AREA"
        if fingers[0] == 1 and sum(fingers[1:]) == 0:
            return "VELOC. MAX" if hand_landmarks.landmark[4].y < hand_landmarks.landmark[0].y - 0.08 else ("VELOC. MIN" if hand_landmarks.landmark[4].y > hand_landmarks.landmark[0].y + 0.08 else "AGUARDANDO...")
        return {0: "EMERGENCIA", 1: "AVANCAR", 2: "GIRAR ESQUERDA", 3: "GIRAR DIREITA", 4: "RECUAR", 5: "PARAR"}.get(total_fingers, "AGUARDANDO...")


class TelemetryPanel:
    def __init__(self, width, height, terrain):
        self.w, self.h, self.px, self.pw, self.terrain = width, height, width - 245, 240, terrain
        self.rover_wheel_wear = [100.0] * 6

        # Fatores físicos de estresse para desgaste assimétrico (FL, FR, ML, MR, RL, RR)
        self.wear_factors = [1.25, 1.20, 0.85, 0.80, 1.10, 1.05]

    def _wheel_color(self, wear):
        if wear > 60: return (0, 255, int(255 * (1 - (wear - 60) / 40)))
        elif wear > 30: return (0, int(255 * (wear - 30) / 30), 255)
        return (0, 0, 255)

    def render(self, frame, t, scanner, command="AGUARDANDO..."):
        px, pw, h = self.px, self.pw, self.h

        overlay = frame.copy()
        cv2.rectangle(overlay, (px-5, 5), (px+pw, h-5), (5, 8, 18), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
        cv2.rectangle(frame, (px-5, 5), (px+pw, h-5), COLORS["panel_border"], 1)

        y = 28
        cv2.putText(frame, "ROVER-01", (px + pw//2 - 38, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, COLORS["orange"], 2)
        cv2.putText(frame, "PAINEL DE MISSAO", (px + pw//2 - 65, y+16), cv2.FONT_HERSHEY_SIMPLEX, 0.30, COLORS["cyan"], 1)
        y += 23; cv2.line(frame, (px, y), (px+pw, y), COLORS["panel_border"], 1); y += 10

        # BAT & TEMP
        for label, val, max_val, color, unit in [("BATERIA", t.battery, 100, t.battery_color, "%"), ("TEMPERATURA", t.temperature, 80, t.temp_color, "C")]:
            pulse = abs(math.sin(time.time() * 5)) if (label=="BATERIA" and val<25) or (label=="TEMPERATURA" and val>55) else 1.0
            cp = tuple(int(c * pulse) for c in color)
            cv2.putText(frame, label, (px + 5, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.32, COLORS["gray"], 1)
            cv2.putText(frame, f"{val:.1f}{unit}" if unit == "C" else f"{val:.0f}{unit}", (px + pw - 46, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, cp, 1)
            y += 16; cv2.rectangle(frame, (px+5, y), (px+pw-5, y+12), (25, 30, 40), -1)
            if (f := int((pw-10) * min(val/max_val, 1.0))) > 0: cv2.rectangle(frame, (px+5, y), (px+5+f, y+12), cp, -1)
            cv2.rectangle(frame, (px+5, y), (px+pw-5, y+12), COLORS["gray"], 1); y += 16

        cv2.line(frame, (px, y), (px+pw, y), COLORS["panel_border"], 1); y += 10

        # NAVEGACAO
        cv2.putText(frame, "NAVEGACAO", (px + pw//2 - 40, y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, COLORS["cyan"], 1); y += 17
        for label, value in [("MISSAO", t.mission_time), ("ODO", f"{t.odometer:.1f} m"), ("X", f"{t.pos_x:+.2f} m"), ("Y", f"{t.pos_y:+.2f} m"), ("DIR", f"{t.heading:.1f} deg")]:
            cv2.putText(frame, f"{label}:", (px+5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.28, COLORS["gray"], 1)
            cv2.putText(frame, value, (px+58, y), cv2.FONT_HERSHEY_SIMPLEX, 0.28, COLORS["white"], 1); y += 14
        cv2.line(frame, (px, y), (px+pw, y), COLORS["panel_border"], 1); y += 8

        # VELOCIDADE
        cv2.putText(frame, "VELOCIDADE", (px + pw//2 - 42, y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, COLORS["cyan"], 1); y += 17
        vc = COLORS["cyan"] if abs(t.speed) > 0 else COLORS["gray"]
        cv2.putText(frame, f"{abs(t.speed):.2f} m/s", (px + pw//2 - 40, y), cv2.FONT_HERSHEY_SIMPLEX, 0.50, vc, 2); y += 16
        bar_x, bar_w, bar_h = px+5, pw-10, 10
        cv2.rectangle(frame, (bar_x, y), (bar_x+bar_w, y+bar_h), (30, 30, 45), -1)
        if (f := int(bar_w * min(abs(t.speed)/10.0, 1.0))) > 0: cv2.rectangle(frame, (bar_x, y), (bar_x+f, y+bar_h), vc, -1)
        lim_x = min(bar_x+bar_w-1, bar_x + int(bar_w * (5.0 * t.speed_mult) / 10.0))
        cv2.line(frame, (lim_x, y-2), (lim_x, y+bar_h+2), t.speed_mode_color, 2)
        cv2.rectangle(frame, (bar_x, y), (bar_x+bar_w, y+bar_h), COLORS["gray"], 1); y += bar_h + 4
        lim_txt = f"LIMITE: {t.speed_mode_label}"
        cv2.putText(frame, lim_txt, (lim_x - cv2.getTextSize(lim_txt, 0, 0.26, 1)[0][0]//2, y+8), 0, 0.26, t.speed_mode_color, 1)
        y += 14; cv2.line(frame, (px, y), (px+pw, y), COLORS["panel_border"], 1); y += 8

        # ── MAPA TOPOGRÁFICO 2D ──
        cv2.putText(frame, "RADAR TOPOGRAFICO 2D", (px + pw//2 - 75, y), cv2.FONT_HERSHEY_SIMPLEX, 0.32, COLORS["cyan"], 1); y += 7
        map_w, map_h, map_cx, map_cy = 220, 110, px + pw//2, y + 110//2
        x1, y1 = map_cx - map_w//2, map_cy - map_h//2
        frame[y1:y1+map_h, x1:x1+map_w] = self.terrain.get_patch_and_update(t.pos_x, t.pos_y, map_w//2, map_h//2)
        cv2.rectangle(frame, (x1, y1), (x1+map_w, y1+map_h), COLORS["panel_border"], 1)

        for t_obj in scanner.targets:
            dx, dy = (t_obj["x"] - t.pos_x) * self.terrain.scale, (t_obj["y"] - t.pos_y) * self.terrain.scale
            t_px, t_py = int(map_cx + dx), int(map_cy - dy)
            if x1 < t_px < x1+map_w and y1 < t_py < y1+map_h:
                cv2.circle(frame, (t_px, t_py), 3, (0, 140, 255), -1)
                cv2.circle(frame, (t_px, t_py), 6, (0, 140, 255), 1)

        slope_c = (0, 60, 255) if t.slope > 1.5 else (0, 255, 120) if t.slope < -1.5 else COLORS["white"]
        cv2.rectangle(frame, (x1+2, y1+2), (x1+100, y1+38), (10, 15, 20), -1)
        cv2.rectangle(frame, (x1+2, y1+2), (x1+100, y1+38), COLORS["panel_border"], 1)
        cv2.putText(frame, f"ELEV: {t.elevation:.1f}m", (x1+8, y1+17), 0, 0.32, COLORS["white"], 1)
        cv2.putText(frame, f"INCL: {t.slope:+.2f} deg", (x1+8, y1+32), 0, 0.32, slope_c, 1)

        rad = math.radians(-t.heading)
        cv2.arrowedLine(frame, (map_cx, map_cy), (map_cx + int(14*math.cos(rad)), map_cy + int(14*math.sin(rad))), COLORS["orange"], 2, tipLength=0.35)
        cv2.circle(frame, (map_cx, map_cy), 4, COLORS["white"], -1)
        y = map_cy + map_h//2 + 10; cv2.line(frame, (px, y), (px+pw, y), COLORS["panel_border"], 1); y += 8

        # ── ROVER CHASSI ──
        cv2.putText(frame, "DIAGNOSTICO CHASSI", (px + pw//2 - 62, y), 0, 0.35, COLORS["cyan"], 1); y += 6
        rm_cy, sc = y + (h - y - 2) // 2, 0.90
        cv2.rectangle(frame, (px, y), (px+pw, h-2), (8, 10, 18), -1)
        for gx in range(px, px+pw, 25): cv2.line(frame, (gx, y), (gx, h-2), (16, 18, 28), 1)
        for gy in range(y, h-2, 25): cv2.line(frame, (px, gy), (px+pw, gy), (16, 18, 28), 1)

        hull = np.array([[map_cx, rm_cy-int(42*sc)], [map_cx+int(18*sc), rm_cy-int(25*sc)], [map_cx+int(22*sc), rm_cy+int(28*sc)], [map_cx+int(12*sc), rm_cy+int(40*sc)], [map_cx-int(12*sc), rm_cy+int(40*sc)], [map_cx-int(22*sc), rm_cy+int(28*sc)], [map_cx-int(18*sc), rm_cy-int(25*sc)]], np.int32)
        cv2.fillPoly(frame, [hull], (20, 25, 30)); cv2.polylines(frame, [hull], True, (60, 90, 110), 2)

        p_col = (0, 120, 180) if t.battery > 30 else (0, 50, 90)
        cv2.rectangle(frame, (map_cx-int(20*sc), rm_cy-int(5*sc)), (map_cx-int(6*sc), rm_cy+int(20*sc)), p_col, -1); cv2.rectangle(frame, (map_cx-int(20*sc), rm_cy-int(5*sc)), (map_cx-int(6*sc), rm_cy+int(20*sc)), (0, 200, 255), 1)
        cv2.rectangle(frame, (map_cx+int(6*sc), rm_cy-int(5*sc)), (map_cx+int(20*sc), rm_cy+int(20*sc)), p_col, -1); cv2.rectangle(frame, (map_cx+int(6*sc), rm_cy-int(5*sc)), (map_cx+int(20*sc), rm_cy+int(20*sc)), (0, 200, 255), 1)

        pulse = abs(math.sin(time.time() * 4))
        cv2.circle(frame, (map_cx, rm_cy+int(8*sc)), int(9*sc), (10, 15, 20), -1); cv2.circle(frame, (map_cx, rm_cy+int(8*sc)), int(5*sc), tuple(int(c * (0.4 + 0.6 * pulse)) for c in (0, 255, 120)), -1)

        cv2.rectangle(frame, (map_cx-int(10*sc), rm_cy-int(38*sc)), (map_cx+int(10*sc), rm_cy-int(32*sc)), (10, 10, 10), -1)
        cv2.circle(frame, (map_cx-int(4*sc), rm_cy-int(35*sc)), 2, (0, 220, 255), -1); cv2.circle(frame, (map_cx+int(4*sc), rm_cy-int(35*sc)), 2, (0, 220, 255), -1)

        for i, (wx, wy) in enumerate([(map_cx-int(36*sc), rm_cy-int(32*sc)), (map_cx+int(36*sc), rm_cy-int(32*sc)), (map_cx-int(36*sc), rm_cy), (map_cx+int(36*sc), rm_cy), (map_cx-int(36*sc), rm_cy+int(32*sc)), (map_cx+int(36*sc), rm_cy+int(32*sc))]):
            wear = self.rover_wheel_wear[i]
            wc = (0, 255, int(255 * (1 - (wear - 60) / 40))) if wear > 60 else (0, int(255 * (wear - 30) / 30), 255) if wear > 30 else (0, 0, 255)

            # Dinâmica asssimétrica e aleatória de desgaste dos pneus
            if command in ("AVANCAR", "RECUAR", "RETORNAR BASE"):
                noise = np.random.uniform(0.9, 1.1)
                self.rover_wheel_wear[i] = max(0, wear - (0.003 * abs(t.speed_mult) * self.wear_factors[i] * noise))

            if command in ("GIRAR ESQUERDA", "GIRAR DIREITA"):
                noise = np.random.uniform(0.9, 1.1)
                turn_stress = 1.6 if i in [0, 1, 4, 5] else 0.4 # Extremidades sofrem mais
                self.rover_wheel_wear[i] = max(0, wear - (0.005 * turn_stress * self.wear_factors[i] * noise))

            ww, wh_r = int(7*sc), int(13*sc)
            cv2.rectangle(frame, (wx-ww, wy-wh_r), (wx+ww, wy+wh_r), tuple(c//4 for c in wc), -1)
            cv2.rectangle(frame, (wx-ww, wy-wh_r), (wx+ww, wy+wh_r), wc, 2)

            if i >= 2 and command in ("AVANCAR", "RETORNAR BASE") and abs(t.speed) > 0.3:
                for p in range(4): cv2.line(frame, (wx-ww+1, wy+wh_r+p*4), (wx+ww-1, wy+wh_r+p*4), tuple(int(c*(1.0-p*0.25)) for c in (0, 200, 80)), 1)
            if command == "EMERGENCIA": cv2.rectangle(frame, (wx-ww, wy-wh_r), (wx+ww, wy+wh_r), (0, 0, 220), 2)

            tx = wx - ww - 26 if i % 2 == 0 else wx + ww + 6
            cv2.putText(frame, ["FL", "FR", "ML", "MR", "RL", "RR"][i], (tx, wy-2), 0, 0.26, wc, 1)
            cv2.putText(frame, f"{wear:.0f}%", (tx, wy+10), 0, 0.24, wc, 1)
            cv2.line(frame, (wx, wy), (map_cx, rm_cy), (25, 50, 25), 1)

        return frame


class SpaceHUD:
    def __init__(self, width, height):
        self.w, self.h       = width, height
        self.command_history = deque(maxlen=5)
        self.stable_command  = "AGUARDANDO..."
        self.stable_buffer   = deque(maxlen=8)
        self.fps_buffer      = deque(maxlen=20)
        self.command_count   = 0

    def get_stable_command(self, raw_command):
        self.stable_buffer.append(raw_command)
        if len(self.stable_buffer) == self.stable_buffer.maxlen:
            most_common = max(set(self.stable_buffer), key=self.stable_buffer.count)
            if most_common != self.stable_command:
                self.stable_command = most_common
                self.command_history.append((most_common, time.strftime("%H:%M:%S")))
                self.command_count += 1
        return self.stable_command

    def render(self, frame, command, fingers_up, fps, hand_detected, ai_msg, scanner):
        stable = self.get_stable_command(command)
        cmd_color = COMMAND_COLORS.get(stable, COLORS["white"])

        overlay = frame.copy()
        cv2.rectangle(overlay, (13, 5), (217, self.h-5), (5, 8, 18), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)
        cv2.rectangle(frame, (5, 5), (225, self.h-5), COLORS["panel_border"], 1)

        cv2.putText(frame, "SPACE", (15, 38), 0, 0.9, COLORS["orange"], 2)
        cv2.putText(frame, "GESTURE CTRL", (15, 58), 0, 0.45, COLORS["cyan"], 1)
        cv2.line(frame, (15, 65), (215, 65), COLORS["panel_border"], 1)

        status_color = COLORS["green"] if hand_detected else COLORS["red"]
        cv2.circle(frame, (25, 82), 6, status_color, -1)
        cv2.putText(frame, "MAO DETECTADA" if hand_detected else "SEM MAO", (38, 87), 0, 0.38, status_color, 1)

        self.fps_buffer.append(fps)
        cv2.putText(frame, f"FPS: {(sum(self.fps_buffer)/len(self.fps_buffer)):.1f}", (38, 105), 0, 0.38, COLORS["gray"], 1)

        cv2.line(frame, (15, 115), (215, 115), COLORS["panel_border"], 1)
        cv2.putText(frame, "GESTOS:", (15, 133), 0, 0.4, COLORS["cyan"], 1)

        for i, (g, d) in enumerate([("0 dedos", "EMERGENCIA"), ("1 dedo", "AVANCAR"), ("2 dedos", "G.ESQ"), ("3 dedos", "G.DIR"),
                                    ("4 dedos", "RECUAR"), ("5 dedos", "PARAR"), ("P. cima", "VEL. MAX"), ("P. baixo", "VEL. MIN"),
                                    ("Hang Loose", "SCAN"), ("Rock Sign", "RET. BASE")]):
            cv2.putText(frame, g, (15, 152+i*18), 0, 0.28, COLORS["gray"], 1); cv2.putText(frame, d, (95, 152+i*18), 0, 0.28, COLORS["white"], 1)

        cv2.line(frame, (15, 342), (215, 342), COLORS["panel_border"], 1)
        cv2.putText(frame, "HISTORICO:", (15, 358), 0, 0.38, COLORS["cyan"], 1)

        for i, (cmd_hist, ts) in enumerate(reversed(list(self.command_history)[-4:])):
            color_h = tuple(int(c * max(0.3, 1.0 - i * 0.2)) for c in COLORS["gray"])
            cv2.putText(frame, f"{ts} {cmd_hist[:11]}", (15, 376+i*20), 0, 0.28, color_h, 1)

        cv2.line(frame, (15, 470), (215, 470), COLORS["panel_border"], 1)
        cv2.putText(frame, "SYNC AI CO-PILOT:", (15, 488), 0, 0.38, COLORS["green"], 1)

        for i, line in enumerate(textwrap.wrap(ai_msg, width=28)):
            line_c = COLORS["red"] if "CRITICO" in ai_msg or "ALERTA" in ai_msg else COLORS["white"]
            cv2.putText(frame, line, (15, 510 + i * 16), 0, 0.32, line_c, 1)

        cv2.line(frame, (15, self.h-50), (215, self.h-50), COLORS["panel_border"], 1)
        cv2.putText(frame, f"CMDS: {self.command_count}", (15, self.h-30), 0, 0.35, COLORS["gray"], 1)

        cx, cy, panel_w, panel_h = self.w // 2, self.h - 90, 340, 75
        cv2.rectangle(frame, (cx-panel_w//2, cy-panel_h//2), (cx+panel_w//2, cy+panel_h//2), (5, 8, 18), -1)
        cv2.rectangle(frame, (cx-panel_w//2, cy-panel_h//2), (cx+panel_w//2, cy+panel_h//2), cmd_color, 2)
        cv2.putText(frame, "COMANDO ATIVO", (cx-65, cy-18), 0, 0.38, COLORS["gray"], 1)

        fs = 0.9 if len(stable) <= 10 else 0.60
        cv2.putText(frame, stable, (cx - cv2.getTextSize(stable, 0, fs, 2)[0][0]//2, cy+18), 0, fs, cmd_color, 2)

        if hand_detected:
            start_x = self.w//2 - (5*28)//2
            for i in range(5):
                dot_x = start_x + i*28
                cv2.circle(frame, (dot_x, 30), 9, COLORS["orange"] if i < fingers_up else COLORS["bg_panel"], -1)
                cv2.circle(frame, (dot_x, 30), 9, COLORS["white"] if i < fingers_up else COLORS["gray"],  1)
            cv2.putText(frame, f"{fingers_up} DEDO(S)", (self.w//2-35, 52), 0, 0.38, COLORS["gray"], 1)

        if scanner.active:
            for i in range(40):
                trail_y = scanner.scan_y - i
                if 0 <= trail_y < self.h:
                    ov = frame.copy(); cv2.line(ov, (230, trail_y), (self.w - 245, trail_y), (0, 255, 80), 1)
                    cv2.addWeighted(ov, (40 - i) / 40 * 0.35, frame, 1 - (40 - i) / 40 * 0.35, 0, frame)
            if 0 <= scanner.scan_y < self.h: cv2.line(frame, (230, scanner.scan_y), (self.w - 245, scanner.scan_y), (0, 255, 80), 2)
            cv2.putText(frame, f"ANALISE GEOLOGICA... {int(scanner.scan_y / self.h * 100)}%", (self.w//2 - 100, 30), 0, 0.6, (0, 255, 80), 2)

        if stable == "EMERGENCIA":
            ov = frame.copy(); cv2.rectangle(ov, (0, 0), (self.w, self.h), (0, 0, int(abs(math.sin(time.time() * 6)) * 255)), -1)
            cv2.addWeighted(ov, 0.15, frame, 0.85, 0, frame)
            cv2.putText(frame, "!! EMERGENCIA !!", (self.w//2-130, 100), 0, 1.0, (0, 0, 255), 3)

        cv2.putText(frame, "FIAP GS 2025 | SPACE CONNECT", (self.w-270, self.h-10), 0, 0.32, COLORS["gray"], 1)

        return frame


def save_mission_report(telemetry, panel, scanner):
    telemetry_file = "MISSION_TELEMETRY_ROVER01.csv"
    scanner_file   = "MISSION_SCANNER_ROVER01.csv"

    try:
        with open(telemetry_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                "Tempo de Missao", "Bateria Restante (%)", "Temperatura Media (C)",
                "Pneu FrenteEsq (%)", "Pneu FrenteDir (%)", "Pneu MeioEsq (%)",
                "Pneu MeioDir (%)", "Pneu TrasEsq (%)", "Pneu TrasDir (%)"
            ])
            avg_temp = telemetry.temp_sum / telemetry.temp_count if telemetry.temp_count > 0 else telemetry.temperature
            wears = [round(w, 1) for w in panel.rover_wheel_wear]
            writer.writerow([telemetry.mission_time, round(telemetry.battery, 1), round(avg_temp, 1), *wears])

        with open(scanner_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Tempo da Missao", "Anomalia/Mineral Detectado", "Coordenada Global X", "Coordenada Global Y"])

            if not scanner.all_discovered_targets:
                writer.writerow(["-", "Nenhuma anomalia geologica detectada na missao", "-", "-"])
            else:
                for tgt in scanner.all_discovered_targets:
                    writer.writerow([tgt["mission_time"], tgt["label"], round(tgt["x"], 2), round(tgt["y"], 2)])

        print(f"\n[SUCESSO] Relatorios salvos com sucesso na pasta atual:\n -> {telemetry_file}\n -> {scanner_file}")
    except Exception as e:
        print(f"\n[ERRO] Falha ao salvar relatorios: {e}")


# ──────────────────────────────────────────────
#  LOOP PRINCIPAL (RODA EM SEGUNDO PLANO)
# ──────────────────────────────────────────────
def run_vision_loop():
    print("=" * 60)
    print("  SPACE GESTURE CONTROL — FIAP Global Solution 2025")
    print("  Controle por Gestos — ROVER-01 (COM API ATIVADA)")
    print("=" * 60)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERRO] Webcam nao encontrada.")
        os._exit(1)

    cap.set(3, 1280); cap.set(4, 720)
    w, h = int(cap.get(3)), int(cap.get(4))

    audio_engine = AIAudioEngine()
    terrain = TerrainMap()
    detector, hud, scanner = GestureDetector(), SpaceHUD(w, h), MartianScanner()
    telemetry, telemetry_panel = RoverTelemetry(), TelemetryPanel(w, h, terrain)
    sync_ai = SyncAI(audio_engine)

    mp_drawing, mp_styles, mp_hands = mp.solutions.drawing_utils, mp.solutions.drawing_styles, mp.solutions.hands
    prev_time, screenshot_count = time.time(), 0

    autopilot_active = False
    shutdown_time = 0

    print("[AGUARDANDO] Mostre sua mao para iniciar...\n")

    while True:
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)

        curr_time = time.time(); fps = 1 / (curr_time - prev_time + 1e-9); prev_time = curr_time
        results = detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        raw_command, fingers_up, hand_detected = "AGUARDANDO...", 0, False

        if results.multi_hand_landmarks:
            hand_detected = True
            for hl, hn_info in zip(results.multi_hand_landmarks, results.multi_handedness):
                mp_drawing.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS, mp_styles.get_default_hand_landmarks_style(), mp_styles.get_default_hand_connections_style())
                fingers_up, fingers = detector.count_fingers(hl, hn_info.classification[0].label)
                raw_command = detector.classify_gesture(fingers_up, fingers, hl)

        if raw_command == "RETORNAR BASE" and shutdown_time == 0:
            if not autopilot_active:
                autopilot_active = True
        elif raw_command not in ["AGUARDANDO...", "RETORNAR BASE", "SCAN AREA"]:
            autopilot_active = False

        if autopilot_active:
            command = "RETORNAR BASE"
            if telemetry.arrived_home and shutdown_time == 0:
                autopilot_active = False
                audio_engine.speak("Chegamos na base com sucesso. Missão finalizada. Desligando o sistema.")
                command = "PARAR"
                shutdown_time = time.time() + 9.0
        elif shutdown_time > 0:
            command = "PARAR"
        else:
            command = raw_command

        telemetry.update(command, terrain)

        if command == "SCAN AREA": scanner.start(h, audio_engine)
        scanner.update(telemetry, h)

        ai_msg = sync_ai.update(telemetry, hud.stable_command, scanner.active)

        frame = hud.render(frame, command, fingers_up, fps, hand_detected, ai_msg, scanner)
        frame = telemetry_panel.render(frame, telemetry, scanner, hud.stable_command)

        # ── ATUALIZANDO O ESTADO GLOBAL DA API ──
        global API_TELEMETRY, API_SCANNER
        API_TELEMETRY["battery"] = round(telemetry.battery, 1)
        API_TELEMETRY["temperature"] = round(telemetry.temperature, 1)
        API_TELEMETRY["speed"] = round(abs(telemetry.speed), 2)
        API_TELEMETRY["status"] = hud.stable_command
        API_TELEMETRY["mission_time"] = telemetry.mission_time
        API_TELEMETRY["pos_x"] = round(telemetry.pos_x, 2)
        API_TELEMETRY["pos_y"] = round(telemetry.pos_y, 2)
        API_TELEMETRY["heading"] = round(telemetry.heading, 1)
        API_TELEMETRY["slope"] = round(telemetry.slope, 2)
        API_TELEMETRY["wheel_wear"] = [round(w, 1) for w in telemetry_panel.rover_wheel_wear]
        API_TELEMETRY["odometer"] = round(telemetry.odometer, 1)  # NOVO
        API_TELEMETRY["signal"] = round(telemetry.signal, 1)  # NOVO


        API_SCANNER = scanner.all_discovered_targets.copy()

        if shutdown_time > 0:
            alpha = min(1.0, max(0.0, (time.time() - (shutdown_time - 4.5)) / 2.0))
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
            cv2.addWeighted(overlay, alpha * 0.85, frame, 1 - (alpha * 0.85), 0, frame)

            cv2.putText(frame, "MISSAO CONCLUIDA", (w//2 - 180, h//2 - 20), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 120), 3)
            cv2.putText(frame, "DESLIGANDO SISTEMA...", (w//2 - 140, h//2 + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 1)

            if time.time() > shutdown_time:
                print("\n[OK] Missao concluida. Encerrando simulacao automaticamente...")
                save_mission_report(telemetry, telemetry_panel, scanner)
                os._exit(0) # Força o encerramento do FastAPI junto com a janela

        cv2.imshow("SPACE GESTURE CONTROL | ROVER-01 | FIAP GS 2025", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            print("\n[OK] Encerrando simulacao...")
            save_mission_report(telemetry, telemetry_panel, scanner)
            os._exit(0)
        elif key == ord("s"):
            cv2.imwrite(f"screenshot_{screenshot_count:03d}.png", frame)
            print(f"[OK] Screenshot {screenshot_count:03d} salva!")
            screenshot_count += 1

    cap.release(); cv2.destroyAllWindows()


# ──────────────────────────────────────────────
#  INICIALIZAÇÃO DUPLA (API + VISÃO)
# ──────────────────────────────────────────────
if __name__ == "__main__":
    vision_thread = threading.Thread(target=run_vision_loop, daemon=True)
    vision_thread.start()

    print("\n[API] Iniciando servidor FastAPI em http://0.0.0.0:8000")
    print("[API] Rotas disponiveis:")
    print("      -> http://localhost:8000/telemetry")
    print("      -> http://localhost:8000/scanner\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)