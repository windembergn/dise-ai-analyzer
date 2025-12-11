import streamlit as st
import google.generativeai as genai
import time
import json
import tempfile
import plotly.graph_objects as go
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="DISE AI Analyzer", page_icon="🫁", layout="centered")

# --- MODELO FIXO ---
MODEL_NAME = "gemini-flash-lite-latest"

# --- GERENCIAMENTO DE API KEY (SECRETS vs MANUAL) ---
api_key = None

with st.sidebar:
    st.title("⚙️ Configuração")
    
    # TENTATIVA SEGURA DE LER SECRETS
    # O bloco try/except impede que o app quebre se não encontrar o arquivo no seu PC
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
            st.success("🔑 API Key detectada no sistema")
    except Exception:
        # Se der erro (arquivo não existe localmente), apenas ignora
        pass
    
    # Se a chave não foi encontrada nos secrets (caso do seu PC), pede manualmente
    if not api_key:
        api_key = st.text_input("Google API Key", type="password")
        if not api_key:
            st.warning("⚠️ Insira a chave ou configure os Secrets.")
            
    st.caption(f"🤖 Modelo Ativo: **{MODEL_NAME}**")

# --- FUNÇÕES ---

def upload_to_gemini(path, mime_type="video/mp4"):
    file = genai.upload_file(path, mime_type=mime_type)
    progress_text = "Enviando para a IA..."
    my_bar = st.progress(0, text=progress_text)
    
    for percent_complete in range(100):
        time.sleep(0.2)
        file = genai.get_file(file.name)
        if file.state.name == "ACTIVE":
            my_bar.empty()
            return file
        if file.state.name == "FAILED":
            my_bar.empty()
            raise ValueError("Falha no processamento do Google.")
        my_bar.progress(percent_complete + 1, text=f"Processando... {file.state.name}")
        
    return file

def analyze_video(file_obj):
    generation_config = {
        "temperature": 0.2, 
        "response_mime_type": "application/json",
    }
    
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        generation_config=generation_config,
        system_instruction="""
        Você é um software médico de precisão para análise de DISE (Drug-Induced Sleep Endoscopy).
        Analise o vídeo para quantificar a obstrução da via aérea.
        
        Saída JSON obrigatória:
        {
            "obstrucao_percentual": (int 0-100),
            "nivel_confianca": (int 0-100),
            "estrutura_colapsada": (string completa, ex: "Palato Mole e Úvula"),
            "padrao_colapso": (string completa, ex: "Concêntrico"),
            "analise_clinica": (string, resumo claro e direto em pt-BR)
        }
        """
    )
    
    response = model.generate_content([
        file_obj, 
        "Analise o grau máximo de obstrução (Nadir) neste vídeo."
    ])
    return json.loads(response.text)

def create_gauge_chart(value):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        title = {'text': "<b>Grau de Obstrução</b>", 'font': {'size': 20}},
        domain = {'x': [0, 1], 'y': [0, 1]},
        gauge = {
            'axis': {'range': [None, 100], 'tickwidth': 1},
            'bar': {'color': "#8B0000"}, 
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "#ddd",
            'steps': [
                {'range': [0, 50], 'color': '#EEF9E7'},
                {'range': [50, 75], 'color': '#FFF4E5'},
                {'range': [75, 100], 'color': '#FDECEC'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': value
            }
        }
    ))
    fig.update_layout(height=280, margin=dict(l=30, r=30, t=50, b=10))
    return fig

# --- INTERFACE ---

st.title("🫁 DISE AI Analyzer")
st.markdown("Monitoramento inteligente de obstrução de vias aéreas.")

uploaded_file = st.file_uploader("", type=["mp4", "mov", "avi"], label_visibility="collapsed")

if uploaded_file is not None:
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') 
    tfile.write(uploaded_file.read())
    
    col_video, col_result = st.columns([1, 1.2]) 
    
    with col_video:
        st.caption("📽️ Vídeo Original")
        st.video(tfile.name)

    with col_result:
        if st.button("🔍 Iniciar Análise", type="primary", use_container_width=True):
            if not api_key:
                st.error("Configure a API Key na barra lateral ou nos Secrets.")
            else:
                try:
                    genai.configure(api_key=api_key)
                    gemini_file = upload_to_gemini(tfile.name)
                    result = analyze_video(gemini_file)
                    
                    st.success("Análise Finalizada")
                    
                    st.plotly_chart(create_gauge_chart(result['obstrucao_percentual']), use_container_width=True)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"""
                        <div style="background-color:#f0f2f6; padding:10px; border-radius:10px; text-align:center;">
                            <span style="font-size:12px; color:#555;">Estrutura</span><br>
                            <span style="font-size:16px; font-weight:bold; color:#333;">{result['estrutura_colapsada']}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with c2:
                        st.markdown(f"""
                        <div style="background-color:#f0f2f6; padding:10px; border-radius:10px; text-align:center;">
                            <span style="font-size:12px; color:#555;">Padrão</span><br>
                            <span style="font-size:16px; font-weight:bold; color:#333;">{result['padrao_colapso']}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.write("") 
                    
                    with st.expander("📝 Laudo Técnico Detalhado", expanded=True):
                        st.write(result['analise_clinica'])
                        st.caption(f"Nível de Confiança da IA: **{result['nivel_confianca']}%**")
                        
                except Exception as e:
                    st.error(f"Erro: {e}")