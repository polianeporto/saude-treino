# -*- coding: utf-8 -*-
"""
Atualiza o dashboard com dados frescos do Garmin Connect.
Roda via GitHub Actions a cada hora.
Usa token OAuth salvo (GARMIN_TOKENS) para evitar bloqueio de IP.
"""
import os
import sys
import json
import datetime
from garminconnect import Garmin

# Força UTF-8 no terminal (Windows pode defaultar para cp1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOKENS_JSON = os.environ.get("GARMIN_TOKENS")
EMAIL = os.environ.get("GARMIN_EMAIL", "")
PASSWORD = os.environ.get("GARMIN_PASSWORD", "")

client = Garmin(EMAIL, PASSWORD)

if TOKENS_JSON:
    # Usa token salvo — sem login interativo, evita bloqueio de IP
    client.client.loads(TOKENS_JSON)
    client._load_profile_and_settings()
    print("Autenticado via token salvo")
else:
    client.login()
    print("Autenticado via usuário/senha")

today = datetime.date.today().isoformat()
now_dt = datetime.datetime.now()
now = now_dt.strftime("%d/%m/%Y às %H:%Mh")
hora_atual = now_dt.hour  # hora local (Brasília via GitHub Actions = UTC-3... ajustar se necessário)

# Busca dados
stats = client.get_stats(today)
sleep_raw = client.get_sleep_data(today)
sleep = sleep_raw.get("dailySleepDTO", {})
scores = sleep.get("sleepScores", {})

# ── Histórico de SpO2 das últimas 14 noites ───────────────────────────────────
historico_spo2 = []
for dias_atras in range(1, 15):
    d = (datetime.date.today() - datetime.timedelta(days=dias_atras)).isoformat()
    try:
        sr = client.get_sleep_data(d)
        dto = sr.get("dailySleepDTO", {})
        spo2_med = dto.get("averageSpO2Value", None)
        spo2_min = dto.get("lowestSpO2Value", None)
        sono_score = (dto.get("sleepScores") or {}).get("overall", {}).get("value", None)
        resp_min = dto.get("lowestRespirationValue", None)
        if spo2_min is not None:
            historico_spo2.append({
                "data": d,
                "spo2_med": spo2_med,
                "spo2_min": spo2_min,
                "sono_score": sono_score,
                "resp_min": resp_min,
                "alerta": spo2_min < 90,
            })
            print(f"   {d}: SpO2 min={spo2_min}% med={spo2_med}%")
    except Exception as e:
        print(f"   {d}: erro — {e}")

# Calcula estatísticas do histórico
mins = [n["spo2_min"] for n in historico_spo2 if n["spo2_min"] is not None]
noites_abaixo_90 = sum(1 for v in mins if v < 90)
spo2_min_absoluto = min(mins) if mins else "--"
spo2_min_media = round(sum(mins) / len(mins), 1) if mins else "--"

try:
    hrv = client.get_hrv_data(today)
    hrv_val = hrv.get("hrvSummary", {}).get("lastNightAvg", "--")
    hrv_status = hrv.get("hrvSummary", {}).get("status", "--")
except Exception:
    hrv_val = "--"
    hrv_status = "--"

# Extrai valores
body_battery = stats.get("bodyBatteryMostRecentValue", "--")
bb_max = stats.get("bodyBatteryHighestValue", "--")
bb_min = stats.get("bodyBatteryLowestValue", "--")
steps = stats.get("totalSteps", 0)
steps_goal = stats.get("dailyStepGoal", 9000)
steps_pct = round((steps / steps_goal) * 100) if steps_goal else 0
fc_repouso = stats.get("restingHeartRate", "--")
estresse = stats.get("averageStressLevel", "--")
spo2_min = stats.get("lowestSpo2", "--")
spo2_media = stats.get("averageSpo2", "--")
calorias = stats.get("activeKilocalories", "--")

sono_h = round(sleep.get("sleepTimeSeconds", 0) / 3600, 1)
sono_score = scores.get("overall", {}).get("value", "--")
sono_qualidade = scores.get("overall", {}).get("qualifierKey", "--")
sono_profundo = round(sleep.get("deepSleepSeconds", 0) / 60)
sono_rem = round(sleep.get("remSleepSeconds", 0) / 60)
sono_leve = round(sleep.get("lightSleepSeconds", 0) / 60)
acordou = sleep.get("awakeCount", "--")
spo2_sono = sleep.get("averageSpO2Value", "--")
spo2_sono_min = sleep.get("lowestSpO2Value", "--")

# Determina feedbacks automáticos
def bb_feedback(val):
    if val == "--": return ("yellow", "⚡ Sem dado")
    if val < 25: return ("red", "🔴 Crítico — só recuperação hoje")
    if val < 40: return ("red", "⚠️ Baixo — treino leve")
    if val < 60: return ("yellow", "⚡ Moderado — cuidado na intensidade")
    return ("green", "✅ Bom — pode treinar")

def sono_feedback(score):
    if score == "--": return ("yellow", "⚡ Sem dado")
    if score < 50: return ("red", "⚠️ Sono ruim — priorize recuperação")
    if score < 70: return ("yellow", "⚡ Sono regular — atenção à intensidade")
    if score < 85: return ("green", "✅ Sono bom")
    return ("green", "✅ Sono excelente")

def spo2_feedback(val):
    if val == "--": return ("yellow", "⚡ Sem dado")
    if val < 88: return ("red", "🔴 Crítico — investigar")
    if val < 90: return ("red", "⚠️ Abaixo de 90% — atenção")
    if val < 94: return ("yellow", "⚡ Levemente baixo")
    return ("green", "✅ Normal")

def fc_feedback(val):
    if val == "--": return ("yellow", "⚡ Sem dado")
    if val < 60: return ("green", "✅ Excelente")
    if val < 70: return ("green", "✅ Saudável")
    if val < 80: return ("yellow", "⚡ Atenção")
    return ("red", "⚠️ Elevada")

def steps_feedback(pct):
    if pct >= 100: return ("green", "✅ Meta batida!")
    if pct >= 60: return ("yellow", "⚡ Bom progresso")
    if pct >= 30: return ("yellow", "⚡ Continue se movendo")
    return ("red", "⚠️ Muito parada hoje")

# Determina orientação do dia
bb_cor, bb_msg = bb_feedback(body_battery if body_battery != "--" else 0)
sono_cor, sono_msg = sono_feedback(sono_score if sono_score != "--" else 0)

if (body_battery != "--" and body_battery < 25) or (sono_score != "--" and sono_score < 50):
    orientacao_cor = "red"
    orientacao_icon = "😴"
    orientacao_titulo = "Dia de descanso ativo"
    orientacao_texto = "Body Battery ou sono muito baixos. Bike leve 20–30 min · FC abaixo de 120 · Sem musculação pesada hoje."
elif (body_battery != "--" and body_battery < 45) or (sono_score != "--" and sono_score < 65):
    orientacao_cor = "yellow"
    orientacao_icon = "⚠️"
    orientacao_titulo = "Treino moderado — sem forçar"
    orientacao_texto = "Sinais de recuperação incompleta. Musculação com carga reduzida · Cardio zona 2 · Sem corrida forte hoje."
else:
    orientacao_cor = "green"
    orientacao_icon = "💪"
    orientacao_titulo = "Pode treinar! Siga a ficha do dia."
    orientacao_texto = "Body Battery e sono em bom nível. Siga a ficha semanal normalmente. Monitore a FC durante o treino."

# Frase do Claude sobre o sono
rem_pct = round((sleep.get("remSleepSeconds", 0) / max(sleep.get("sleepTimeSeconds", 1), 1)) * 100)

if sono_score != "--" and sono_score >= 80:
    frase_sono = f"Boa noite de sono! Você dormiu {sono_h}h com score {sono_score} — seu corpo recuperou bem. Aproveite o dia."
elif sono_score != "--" and sono_score >= 65:
    frase_sono = f"Noite razoável — {sono_h}h dormidas, score {sono_score}. Deu pra recuperar mas não foi o ideal. Atenção à intensidade hoje."
elif sono_score != "--":
    frase_sono = f"Noite difícil: apenas {sono_h}h com score {sono_score} e {sono_rem} min de REM ({rem_pct}%). Seu corpo não recuperou de verdade — hoje é dia de poupar energia."
else:
    frase_sono = "Não foi possível ler os dados de sono desta noite."

# ── Verifica se já fez atividade hoje ─────────────────────────────────────────
# Plano semanal: dia da semana → tipo esperado e horário de lembrete
PLANO_SEMANA = {
    0: {"nome": "Costas + Ombro",       "tipo": "musculacao", "lembrar_apos": 17},  # Segunda
    1: {"nome": "Cardio Leve + Abs",    "tipo": "bike",       "lembrar_apos": 17},  # Terça
    2: {"nome": "Quadríceps + Adução",  "tipo": "musculacao", "lembrar_apos": 17},  # Quarta
    3: {"nome": "Bíceps + Peito",       "tipo": "musculacao", "lembrar_apos": 17},  # Quinta
    4: {"nome": "Glúteos ★",            "tipo": "musculacao", "lembrar_apos": 17},  # Sexta
    5: {"nome": "Descanso ou Livre",    "tipo": "livre",      "lembrar_apos": 99},  # Sábado
    6: {"nome": "Quadríceps + Adução",  "tipo": "musculacao", "lembrar_apos": 15},  # Domingo
}

dia_semana = now_dt.weekday()  # 0=segunda … 6=domingo
treino_hoje = PLANO_SEMANA.get(dia_semana, {})
treino_nome_hoje = treino_hoje.get("nome", "")
lembrar_apos = treino_hoje.get("lembrar_apos", 17)

# Hora de Brasília = UTC-3 (GitHub Actions roda em UTC)
import os as _os
hora_brasilia = hora_atual - 3  # ajuste simples; em produção usar pytz se necessário

atividade_feita = False
cardio_feito = False
musculacao_feita = False
minutos_ativos_hoje = 0

try:
    atividades_hoje = client.get_activities_by_date(today, today, activitytype=None)
    for a in atividades_hoje:
        tipo = (a.get("activityType", {}).get("typeKey") or "").lower()
        duracao = a.get("duration", 0) or 0
        if duracao > 300:  # mais de 5 min conta
            atividade_feita = True
            minutos_ativos_hoje += round(duracao / 60)
            if any(k in tipo for k in ["cycling", "bike", "indoor_cycling"]):
                cardio_feito = True
            if any(k in tipo for k in ["strength", "fitness_equipment", "cardio"]):
                musculacao_feita = True
    print(f"   Atividades hoje: {len(atividades_hoje)} | musculação={musculacao_feita} | bike={cardio_feito}")
except Exception as e:
    print(f"   Aviso: não foi possível buscar atividades de hoje — {e}")

# Define alerta de treino
alerta_treino = ""
alerta_treino_urgente = False

if hora_brasilia >= lembrar_apos:
    tipo_esperado = treino_hoje.get("tipo", "")
    if tipo_esperado == "bike" and not cardio_feito and not atividade_feita:
        alerta_treino = f"Ainda não fez a bike hoje! Vai lá — 20 a 30 minutos, FC abaixo de 130 bpm. Você consegue 💪"
        alerta_treino_urgente = hora_brasilia >= 20
    elif tipo_esperado == "musculacao" and not musculacao_feita and not atividade_feita:
        alerta_treino = f"Treino de hoje: {treino_nome_hoje}. Você ainda não registrou nenhuma atividade. Vai treinar hoje?"
        alerta_treino_urgente = hora_brasilia >= 20

# Gera o data.js
# ── Análise das últimas 7 noites para o card Claude ──────────────────────────
historico_7 = historico_spo2[:7]  # já coletado acima
scores_7     = [n["sono_score"] for n in historico_7 if n["sono_score"]]
mins_spo2_7  = [n["spo2_min"]   for n in historico_7 if n["spo2_min"]]
noites_sem_rem = 0  # calculado abaixo

sono_media_7     = round(sum(scores_7) / len(scores_7)) if scores_7 else "--"
spo2_noites_7    = sum(1 for v in mins_spo2_7 if v < 90)
data_inicio      = historico_7[-1]["data"] if historico_7 else today
d_ini            = datetime.datetime.strptime(data_inicio, "%Y-%m-%d")
data_inicio_fmt  = d_ini.strftime("%d/%m")
data_hoje_fmt    = datetime.date.today().strftime("%d/%m/%Y")

# Tag e frase da análise noturna (usando dados de hoje)
if sono_score != "--" and sono_score >= 80:
    tag_sono = "Sono Bom"
    tag_cor  = "green"
    frase_claude_noite = f"Boa noite! {sono_h}h de sono com score {sono_score}. Body Battery ao acordar em boa forma. Aproveite o dia com intensidade normal."
elif sono_score != "--" and sono_score >= 65:
    tag_sono = "Sono Regular"
    tag_cor  = "yellow"
    frase_claude_noite = f"Noite razoável — {sono_h}h, score {sono_score}. REM de {sono_rem} min. Deu pra recuperar, mas atenção à intensidade do treino hoje."
elif sono_score != "--":
    tag_sono = "Sono Ruim"
    tag_cor  = "red"
    frase_claude_noite = f"Noite difícil: {sono_h}h com score {sono_score} e apenas {sono_rem} min de REM. Seu corpo não recuperou de verdade — reduza a carga hoje."
else:
    tag_sono = "Sem dado"
    tag_cor  = "yellow"
    frase_claude_noite = "Não foi possível ler os dados de sono desta noite."

detalhe_noite = f"Sono REM: {sono_rem} min · SpO2 mínimo: {spo2_min}% · Body Battery: {body_battery} · Estresse médio: {estresse}/100"

# Frase da análise semanal
if sono_media_7 != "--" and sono_media_7 >= 75 and spo2_noites_7 <= 2:
    tag_semana = "Boa semana"
    tag_cor_semana = "green"
    frase_claude_semana = f"Semana sólida! Sono médio {sono_media_7}/100 e SpO2 abaixo de 90% em apenas {spo2_noites_7} noites. Continue nesse ritmo."
elif spo2_noites_7 >= 5:
    tag_semana = "Atenção"
    tag_cor_semana = "red"
    frase_claude_semana = f"SpO2 abaixo de 90% em {spo2_noites_7} das últimas 7 noites — padrão consistente de dessaturação. Prioridade: consulta com pneumologista e polissonografia."
else:
    tag_semana = "Atenção"
    tag_cor_semana = "yellow"
    frase_claude_semana = f"Sono médio de {sono_media_7}/100 nas últimas 7 noites. SpO2 abaixo de 90% em {spo2_noites_7} noites. Recuperação incompleta afeta diretamente seu ganho de massa."

detalhe_semana = f"Score médio: {sono_media_7}/100 · SpO2 abaixo de 90%: {spo2_noites_7}/7 noites · SpO2 mínimo do período: {spo2_min_absoluto}% · Período: {data_inicio_fmt} → {data_hoje_fmt}"

resumo_personal = f"""📋 Resumo diário — Poli ({now})

⚡ Body Battery: {body_battery}/100 — {bb_msg}
😴 Sono: {sono_h}h · score {sono_score} — {sono_msg}
❤️ FC repouso: {fc_repouso} bpm
🚶 Passos: {steps}/{steps_goal} ({steps_pct}%)
🫁 SpO2 mínimo: {spo2_min}%
📊 Estresse médio: {estresse}/100

🏋️ Treino de hoje: {treino_nome_hoje}
🎯 Orientação: {orientacao_titulo} — {orientacao_texto}"""

data = {
    "atualizado": now,
    "resumo_personal": resumo_personal,
    "tag_sono": tag_sono,
    "tag_cor": tag_cor,
    "frase_claude_noite": frase_claude_noite,
    "detalhe_noite": detalhe_noite,
    "tag_semana": tag_semana,
    "tag_cor_semana": tag_cor_semana,
    "frase_claude_semana": frase_claude_semana,
    "detalhe_semana": detalhe_semana,
    "data_hoje_fmt": data_hoje_fmt,
    "data_inicio_fmt": data_inicio_fmt,
    "hoje": today,
    "body_battery": body_battery,
    "bb_max": bb_max,
    "bb_min": bb_min,
    "bb_feedback_cor": bb_cor,
    "bb_feedback_msg": bb_msg,
    "steps": f"{steps:,.0f}".replace(",", "."),
    "steps_goal": f"{steps_goal:,.0f}".replace(",", "."),
    "steps_pct": steps_pct,
    "steps_feedback_cor": steps_feedback(steps_pct)[0],
    "steps_feedback_msg": steps_feedback(steps_pct)[1],
    "fc_repouso": fc_repouso,
    "fc_feedback_cor": fc_feedback(fc_repouso if fc_repouso != "--" else 70)[0],
    "fc_feedback_msg": fc_feedback(fc_repouso if fc_repouso != "--" else 70)[1],
    "estresse": estresse,
    "spo2_min": spo2_min,
    "spo2_media": spo2_media,
    "spo2_feedback_cor": spo2_feedback(spo2_min if spo2_min != "--" else 95)[0],
    "spo2_feedback_msg": spo2_feedback(spo2_min if spo2_min != "--" else 95)[1],
    "hrv_val": hrv_val,
    "hrv_status": hrv_status,
    "calorias": calorias,
    "sono_h": sono_h,
    "sono_score": sono_score,
    "sono_qualidade": sono_qualidade,
    "sono_profundo": sono_profundo,
    "sono_rem": sono_rem,
    "sono_leve": sono_leve,
    "acordou": acordou,
    "spo2_sono": spo2_sono,
    "spo2_sono_min": spo2_sono_min,
    "sono_feedback_cor": sono_cor,
    "sono_feedback_msg": sono_msg,
    "frase_sono": frase_sono,
    "orientacao_cor": orientacao_cor,
    "orientacao_icon": orientacao_icon,
    "orientacao_titulo": orientacao_titulo,
    "orientacao_texto": orientacao_texto,
    "historico_spo2": historico_spo2,
    "spo2_noites_abaixo_90": noites_abaixo_90,
    "spo2_min_absoluto": spo2_min_absoluto,
    "spo2_min_media": spo2_min_media,
    "treino_nome_hoje": treino_nome_hoje,
    "atividade_feita": atividade_feita,
    "cardio_feito": cardio_feito,
    "musculacao_feita": musculacao_feita,
    "minutos_ativos_hoje": minutos_ativos_hoje,
    "alerta_treino": alerta_treino,
    "alerta_treino_urgente": alerta_treino_urgente,
    "hora_brasilia": hora_brasilia,
}

with open("data.js", "w", encoding="utf-8") as f:
    f.write(f"const GARMIN = {json.dumps(data, ensure_ascii=False, indent=2)};\n")

print(f"✅ Dashboard atualizado em {now}")
print(f"   Body Battery: {body_battery} | Sono: {sono_h}h score {sono_score} | Passos: {steps}")
