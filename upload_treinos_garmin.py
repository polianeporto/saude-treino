# -*- coding: utf-8 -*-
"""
Cria os treinos do novo protocolo (Protocolo_Treinamento_Poliane_Porto.xlsx)
como workouts estruturados de verdade no Garmin Connect, pra aparecer no
relógio durante o treino.

Uso:
    python upload_treinos_garmin.py A          # cria só o Treino A (teste)
    python upload_treinos_garmin.py A B C PANTURRILHA ABDOMINAL
    python upload_treinos_garmin.py --all

Credenciais: mesmas variáveis de ambiente do update_dashboard.py
(GARMIN_EMAIL, GARMIN_PASSWORD, GARMIN_TOKENS).

Formato do JSON de workout (sportTypeId 5 "strength_training",
RepeatGroupDTO para séries uniformes, ExecutableStepDTO sequenciais para
séries com reps variáveis) documentado em:
https://github.com/n1t3k/garmin-strength-api

Categoria/exerciseName vêm do catálogo oficial do FIT SDK (via
github.com/tormoder/fit, gerado a partir do Profile.xlsx da Garmin).
Exercícios sem equivalente exato no catálogo (ex: cadeira extensora,
cadeira adutora/abdutora, agachamento no Smith, desenvolvimento/elevação
lateral/crucifixo em máquina — a Garmin não tem categoria própria pra
esses aparelhos) ficam sem "category"/"exerciseName" (aparecem como
exercício genérico no relógio) e levam o nome real em "description".
"""
import os
import sys
import json
from garminconnect import Garmin

REST_DEFAULT_ABS_CALF = 45  # a planilha não especifica descanso pros extras de abdominal/panturrilha


def exercicio(nome_pt, rest_s, category=None, exercise_name=None,
              reps_uniforme=None, sets_uniforme=None, reps_sequencia=None,
              tempo_s=None, nota=""):
    """Descreve um exercício; vira RepeatGroupDTO (reps/sets iguais em
    todas as séries) ou uma sequência de ExecutableStepDTO (reps
    diferentes por série, ex: 15/15/10/10)."""
    return {
        "nome_pt": nome_pt,
        "category": category,
        "exercise_name": exercise_name,
        "reps_uniforme": reps_uniforme,
        "sets_uniforme": sets_uniforme,
        "reps_sequencia": reps_sequencia,
        "tempo_s": tempo_s,
        "rest_s": rest_s,
        "nota": nota,
    }


TREINO_A = [
    exercicio("Cadeira Extensora", rest_s=60, reps_sequencia=[15, 15, 10, 10],
              nota="Pico de contração de 2s nas duas primeiras séries + 2x com carga máxima. "
                   "Sem exercício exato de cadeira extensora no catálogo do Garmin."),
    exercicio("Leg Press 45°", rest_s=60, category="SQUAT", exercise_name="LEG_PRESS",
              reps_uniforme=12, sets_uniforme=3,
              nota="Priorizar uma boa amplitude (12 a 15 reps)"),
    exercicio("Agachamento no Smith", rest_s=60, reps_sequencia=[15, 10, 10, 10],
              nota="Descer até o talo — usar a trava de segurança. "
                   "Sem agachamento no Smith no catálogo do Garmin."),
    exercicio("Stiff com os Pés Abduzidos", rest_s=60, category="DEADLIFT",
              exercise_name="BARBELL_STRAIGHT_LEG_DEADLIFT",
              reps_uniforme=12, sets_uniforme=3,
              nota="Pés abduzidos. Pico de contração (12 a 15 reps)"),
    exercicio("Mesa Flexora", rest_s=60, category="LEG_CURL", exercise_name="LEG_CURL",
              reps_uniforme=12, sets_uniforme=4, nota="12 a 15 reps"),
    exercicio("Cadeira Adutora", rest_s=60, reps_uniforme=10, sets_uniforme=4,
              nota="Sem cadeira adutora no catálogo do Garmin."),
]

TREINO_B = [
    exercicio("Desenvolvimento na Máquina", rest_s=40, reps_uniforme=12, sets_uniforme=3,
              nota="12 a 15 reps. Sem desenvolvimento em máquina no catálogo do Garmin."),
    exercicio("Elevação Lateral com Halteres", rest_s=20, reps_uniforme=15, sets_uniforme=6,
              nota="Atenção ao tempo de descanso (20s). "
                   "Sem elevação lateral em pé exata no catálogo do Garmin."),
    exercicio("Crucifixo Invertido no Voador", rest_s=40, reps_uniforme=12, sets_uniforme=4,
              nota="Pegada pronada, pico de contração de 2s em todas as reps (12 a 15). "
                   "Sem crucifixo invertido em máquina (peck-deck) no catálogo do Garmin."),
    exercicio("Remada na Máquina Peg. Pronada Aberta", rest_s=60, category="ROW",
              exercise_name="WIDE_GRIP_SEATED_CABLE_ROW",
              reps_sequencia=[15, 10, 10, 10],
              nota="Pico de contração de 2s em todas as reps"),
    exercicio("Face Pull com a Corda", rest_s=40, category="ROW", exercise_name="FACE_PULL",
              reps_uniforme=12, sets_uniforme=3,
              nota="Pico de contração de 2s em todas as reps (12 a 15)"),
    exercicio("Pulley Frente Peg. Pronada Aberta", rest_s=40, category="PULL_UP",
              exercise_name="WIDE_GRIP_LAT_PULLDOWN",
              reps_sequencia=[15, 10, 10]),
    exercicio("Pull Down Barra \"W\"", rest_s=40, category="PULL_UP",
              exercise_name="STRAIGHT_ARM_PULLDOWN",
              reps_uniforme=12, sets_uniforme=3, nota="12 a 15 reps"),
]

TREINO_C = [
    exercicio("Cadeira Abdutora em 45°", rest_s=40, reps_uniforme=15, sets_uniforme=5,
              nota="Ativação — carga leve. Sem cadeira abdutora no catálogo do Garmin."),
    exercicio("Extensão de Quadril com a Perna Cruzada", rest_s=60, category="HIP_RAISE",
              exercise_name="HIP_EXTENSION_AND_CROSS",
              reps_uniforme=12, sets_uniforme=3, nota="Não gangorrar o quadril"),
    exercicio("Elevação Pélvica", rest_s=120, category="HIP_RAISE",
              exercise_name="BARBELL_HIP_THRUST_WITH_BENCH",
              reps_sequencia=[15, 15, 10, 10],
              nota="Pico de contração de 2s nas duas primeiras séries, depois suba a carga"),
    exercicio("Terra Sumô", rest_s=120, category="DEADLIFT", exercise_name="SUMO_DEADLIFT",
              reps_sequencia=[15, 10, 10], nota="Carga máxima"),
    exercicio("Búlgaro", rest_s=60, category="LUNGE", exercise_name="DUMBBELL_BULGARIAN_SPLIT_SQUAT",
              reps_uniforme=10, sets_uniforme=3),
    exercicio("Stiff com os Pés Abduzidos", rest_s=120, category="DEADLIFT",
              exercise_name="BARBELL_STRAIGHT_LEG_DEADLIFT",
              reps_sequencia=[15, 10, 10, 10]),
]

EXTRA_PANTURRILHA = [
    exercicio("Panturrilha Sentado (Banco/Sóleo)", rest_s=REST_DEFAULT_ABS_CALF,
              category="CALF_RAISE", exercise_name="SEATED_CALF_RAISE",
              reps_uniforme=12, sets_uniforme=3,
              nota="Descanso não especificado na planilha — ajustado para 45s"),
    exercicio("Panturrilha no Leg Horizontal", rest_s=REST_DEFAULT_ABS_CALF,
              category="CALF_RAISE", exercise_name="STANDING_CALF_RAISE",
              reps_uniforme=12, sets_uniforme=3,
              nota="Realizada no leg press horizontal"),
]

EXTRA_ABDOMINAL = [
    exercicio("Abdominal Reto Curto no Solo", rest_s=15, category="CRUNCH",
              exercise_name="CRUNCH", reps_uniforme=20, sets_uniforme=4,
              nota="Bi-set com a infra sanfona"),
    exercicio("Infra Sanfona no Solo", rest_s=REST_DEFAULT_ABS_CALF, category="CRUNCH",
              exercise_name="REVERSE_CRUNCH", reps_uniforme=10, sets_uniforme=4,
              nota="Bi-set com o abdominal reto — alterne entre os dois"),
    exercicio("Prancha", rest_s=REST_DEFAULT_ABS_CALF, category="PLANK", exercise_name="PLANK",
              tempo_s=60, sets_uniforme=4,
              nota="Descanso não especificado na planilha — ajustado para 45s"),
]

WORKOUTS = {
    "A": ("Protocolo Poli — A: Coxa Completa", TREINO_A),
    "B": ("Protocolo Poli — B: Superiores Completo", TREINO_B),
    "C": ("Protocolo Poli — C: Glúteo e Posterior de Coxa", TREINO_C),
    "PANTURRILHA": ("Protocolo Poli — Extra: Panturrilha", EXTRA_PANTURRILHA),
    "ABDOMINAL": ("Protocolo Poli — Extra: Abdominal", EXTRA_ABDOMINAL),
}

SPORT_TYPE = {"sportTypeId": 5, "sportTypeKey": "strength_training", "displayOrder": 5}
STEP_TYPE_REPEAT = {"stepTypeId": 6, "stepTypeKey": "repeat", "displayOrder": 6}
STEP_TYPE_INTERVAL = {"stepTypeId": 3, "stepTypeKey": "interval", "displayOrder": 3}
STEP_TYPE_REST = {"stepTypeId": 5, "stepTypeKey": "rest", "displayOrder": 5}
COND_ITERATIONS = {"conditionTypeId": 7, "conditionTypeKey": "iterations", "displayOrder": 7, "displayable": False}
COND_REPS = {"conditionTypeId": 10, "conditionTypeKey": "reps", "displayOrder": 10, "displayable": True}
COND_TIME = {"conditionTypeId": 2, "conditionTypeKey": "time", "displayOrder": 2, "displayable": True}
TARGET_NONE = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target", "displayOrder": 1}


def passo_exercicio(step_order, ex, end_condition, end_value):
    step = {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": STEP_TYPE_INTERVAL,
        "endCondition": end_condition,
        "endConditionValue": float(end_value),
        "targetType": TARGET_NONE,
    }
    if ex["category"] and ex["exercise_name"]:
        step["category"] = ex["category"]
        step["exerciseName"] = ex["exercise_name"]
    descricao = ex["nome_pt"] if not (ex["category"] and ex["exercise_name"]) else None
    if ex["nota"] or descricao:
        step["description"] = " — ".join(p for p in [descricao, ex["nota"]] if p)
    return step


def passo_descanso(step_order, rest_s):
    return {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": STEP_TYPE_REST,
        "endCondition": COND_TIME,
        "endConditionValue": float(rest_s),
        "targetType": TARGET_NONE,
    }


def construir_passos(ex, step_order):
    """Retorna (lista_de_passos, proximo_step_order)."""
    passos = []
    end_condition = COND_TIME if ex["tempo_s"] is not None else COND_REPS
    end_value_uniforme = ex["tempo_s"] if ex["tempo_s"] is not None else ex["reps_uniforme"]

    if ex["reps_sequencia"]:
        # Reps variam a cada série (ex: 15/15/10/10) — não dá pra usar
        # RepeatGroupDTO (que assume o mesmo alvo em todas as iterações),
        # então viram passos sequenciais, um por série.
        for i, reps in enumerate(ex["reps_sequencia"]):
            passos.append(passo_exercicio(step_order, ex, COND_REPS, reps))
            step_order += 1
            if i < len(ex["reps_sequencia"]) - 1:
                passos.append(passo_descanso(step_order, ex["rest_s"]))
                step_order += 1
        return passos, step_order

    # Séries uniformes — um único RepeatGroupDTO com N iterações
    sets = ex["sets_uniforme"]
    grupo_order = step_order
    step_order += 1
    sub_passos = [passo_exercicio(step_order, ex, end_condition, end_value_uniforme)]
    step_order += 1
    sub_passos.append(passo_descanso(step_order, ex["rest_s"]))
    step_order += 1
    grupo = {
        "type": "RepeatGroupDTO",
        "stepOrder": grupo_order,
        "stepType": STEP_TYPE_REPEAT,
        "numberOfIterations": sets,
        "endCondition": COND_ITERATIONS,
        "endConditionValue": float(sets),
        "skipLastRestStep": True,
        "smartRepeat": False,
        "workoutSteps": sub_passos,
    }
    return [grupo], step_order


def construir_workout(nome, exercicios):
    passos = []
    step_order = 1
    for ex in exercicios:
        novos_passos, step_order = construir_passos(ex, step_order)
        passos.extend(novos_passos)

    sem_match = [ex["nome_pt"] for ex in exercicios if not (ex["category"] and ex["exercise_name"])]

    workout = {
        "sportType": SPORT_TYPE,
        "workoutName": nome,
        "description": "Gerado a partir do Protocolo_Treinamento_Poliane_Porto.xlsx",
        "workoutSegments": [{
            "segmentOrder": 1,
            "sportType": SPORT_TYPE,
            "workoutSteps": passos,
        }],
    }
    return workout, sem_match


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    tokens_json = os.environ.get("GARMIN_TOKENS")
    email = os.environ.get("GARMIN_EMAIL", "")
    password = os.environ.get("GARMIN_PASSWORD", "")
    client = Garmin(email, password)
    if tokens_json:
        client.client.loads(tokens_json)
        client._load_profile_and_settings()
        print("Autenticado via token salvo")
    else:
        client.login()
        print("Autenticado via usuário/senha")

    if "--delete" in args:
        ids = [a for a in args if a != "--delete"]
        for workout_id in ids:
            client.delete_workout(workout_id)
            print(f"🗑️  Removido — workoutId: {workout_id}")
        return

    if "--wipe-and-create" in args:
        existentes = []
        start = 0
        while True:
            pagina = client.get_workouts(start=start, limit=100)
            if not pagina:
                break
            existentes.extend(pagina)
            if len(pagina) < 100:
                break
            start += 100
        print(f"\n=== Encontrados {len(existentes)} treino(s) salvos no Garmin Connect ===")
        for w in existentes:
            print(f"   - {w.get('workoutName')} (workoutId: {w.get('workoutId')})")
        for w in existentes:
            client.delete_workout(w["workoutId"])
        print(f"🗑️  Removidos todos os {len(existentes)} treino(s) anteriores.")
        chaves = list(WORKOUTS.keys())
    else:
        chaves = list(WORKOUTS.keys()) if "--all" in args else [a.upper() for a in args]

    for chave in chaves:
        if chave not in WORKOUTS:
            print(f"⚠️  Treino '{chave}' não reconhecido — opções: {list(WORKOUTS.keys())}")
            continue
        nome, exercicios = WORKOUTS[chave]
        workout_json, sem_match = construir_workout(nome, exercicios)
        print(f"\n=== Enviando '{nome}' ===")
        if sem_match:
            print(f"   (sem exercício exato no catálogo do Garmin: {', '.join(sem_match)})")
        resposta = client.upload_workout(workout_json)
        workout_id = resposta.get("workoutId") if isinstance(resposta, dict) else None
        print(f"   ✅ Criado — workoutId: {workout_id}")


if __name__ == "__main__":
    main()
