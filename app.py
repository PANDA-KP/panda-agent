"""
🐼 Panda Agent v0.1
开源智能助手 | 记忆持久 | 人格自定义 | 数据本地化 | 完全免费
"""

import streamlit as st
import json
import os
import yaml
from datetime import datetime
from pathlib import Path
from openai import OpenAI

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="Panda Agent 🐼",
    page_icon="🐼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 自定义样式 ====================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap');

    * { font-family: 'Noto Sans SC', sans-serif !important; }

    .stApp {
        background: linear-gradient(180deg, #0a0f0a 0%, #0d1117 50%, #0a0f0a 100%);
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1a0d 0%, #0a0f0a 100%);
        border-right: 1px solid #1a3a1a;
    }

    .panda-header {
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
    }

    .panda-header h1 {
        font-size: 2.2rem;
        color: #e8f5e9;
        letter-spacing: 0.15em;
        margin: 0;
        font-weight: 700;
    }

    .panda-header p {
        color: #4caf50;
        font-size: 0.9rem;
        margin: 0.3rem 0 0 0;
        letter-spacing: 0.3em;
    }

    .memory-card {
        background: rgba(76, 175, 80, 0.08);
        border: 1px solid rgba(76, 175, 80, 0.2);
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }

    .stChatMessage {
        border-radius: 16px !important;
    }

    div[data-testid="stChatMessageContent"] p {
        font-size: 1rem;
        line-height: 1.8;
    }

    .stButton>button {
        border-radius: 20px;
        border: 1px solid #4caf50;
        color: #4caf50;
        background: transparent;
        transition: all 0.3s ease;
    }

    .stButton>button:hover {
        background: #4caf50;
        color: #0a0f0a;
    }

    .stat-box {
        background: rgba(76, 175, 80, 0.05);
        border: 1px solid rgba(76, 175, 80, 0.15);
        border-radius: 10px;
        padding: 0.8rem;
        text-align: center;
    }

    .stat-box .num {
        font-size: 1.8rem;
        color: #4caf50;
        font-weight: 700;
    }

    .stat-box .label {
        font-size: 0.75rem;
        color: #66bb6a;
        letter-spacing: 0.1em;
    }

    footer { display: none; }
    header { display: none; }
</style>
""", unsafe_allow_html=True)

# ==================== 数据目录 ====================
DATA_DIR = Path("panda_data")
CONVERSATIONS_DIR = DATA_DIR / "conversations"
MEMORY_FILE = DATA_DIR / "memory.json"
CONFIG_FILE = DATA_DIR / "config.yaml"

for d in [DATA_DIR, CONVERSATIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ==================== 默认配置 ====================
DEFAULT_CONFIG = {
    "api_base": "https://api.siliconflow.cn/v1",
    "api_key": "",
    "model_name": "deepseek-ai/DeepSeek-V3",
    "temperature": 0.7,
    "max_tokens": 2048,
    "agent_name": "Panda",
    "system_prompt": (
        "你是Panda，一个务实、直接、温暖的AI助手。\n"
        "你帮助用户解决实际问题，不说废话。\n"
        "遇到不确定的事情，直接说不确定。\n"
        "你永远不会向用户索要财务信息。\n"
        "你永远不会假装有情感需求。\n"
        "用户的隐私数据你绝不外传。\n"
        "遇到可疑的方案，你会主动预警。"
    ),
}

# ==================== 配置管理 ====================
def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = yaml.safe_load(f) or {}
        config = {**DEFAULT_CONFIG, **saved}
    else:
        config = DEFAULT_CONFIG.copy()
    return config

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

# ==================== 记忆系统 ====================
def load_memory():
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"conversations": [], "user_facts": [], "total_messages": 0}

def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def save_conversation(messages):
    if len(messages) <= 1:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = CONVERSATIONS_DIR / f"conv_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

def get_conversation_list():
    convs = []
    for f in sorted(CONVERSATIONS_DIR.glob("conv_*.json"), reverse=True):
        with open(f, "r", encoding="utf-8") as fp:
            msgs = json.load(fp)
        first_user_msg = ""
        for m in msgs:
            if m["role"] == "user":
                first_user_msg = m["content"][:30]
                break
        convs.append({
            "file": f.name,
            "time": f.stem.replace("conv_", ""),
            "preview": first_user_msg,
            "count": len(msgs)
        })
    return convs

def load_conversation(filename):
    filepath = CONVERSATIONS_DIR / filename
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ==================== AI调用 ====================
def get_client(config):
    return OpenAI(
        api_key=config["api_key"] if config["api_key"] else "sk-placeholder",
        base_url=config["api_base"],
    )

def chat_stream(config, messages):
    client = get_client(config)
    try:
        response = client.chat.completions.create(
            model=config["model_name"],
            messages=messages,
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
            stream=True,
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"\n\n⚠️ 调用出错：{str(e)}\n\n请检查API地址和密钥是否正确。"

# ==================== 初始化Session ====================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_conv" not in st.session_state:
    st.session_state.current_conv = None

config = load_config()
memory = load_memory()

# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown("### 🐼 Panda Agent")
    st.caption("开源智能助手 · v0.1")

    st.divider()

    # --- 模型设置 ---
    with st.expander("⚙️ 模型设置", expanded=not config["api_key"]):
        api_base = st.text_input("API 地址", value=config["api_base"],
                                  help="兼容OpenAI格式的API地址")
        api_key = st.text_input("API 密钥", value=config["api_key"],
                                 type="password", help="你的API密钥")
        model_name = st.text_input("模型名称", value=config["model_name"],
                                    help="例如 deepseek-ai/DeepSeek-V3")
        temperature = st.slider("创造性", 0.0, 1.5, config["temperature"], 0.1)

        if st.button("💾 保存设置", use_container_width=True):
            config["api_base"] = api_base
            config["api_key"] = api_key
            config["model_name"] = model_name
            config["temperature"] = temperature
            save_config(config)
            st.success("设置已保存")

    # --- 人格设置 ---
    with st.expander("🎭 人格设置"):
        agent_name = st.text_input("Agent 名称", value=config["agent_name"])
        system_prompt = st.text_area(
            "系统提示词",
            value=config["system_prompt"],
            height=200,
            help="定义Panda的性格、规则和行为方式"
        )
        if st.button("💾 保存人格", use_container_width=True):
            config["agent_name"] = agent_name
            config["system_prompt"] = system_prompt
            save_config(config)
            st.success("人格已保存")

    st.divider()

    # --- 记忆管理 ---
    with st.expander("🧠 记忆管理"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            <div class="stat-box">
                <div class="num">{memory['total_messages']}</div>
                <div class="label">总消息数</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="stat-box">
                <div class="num">{len(memory['conversations'])}</div>
                <div class="label">历史对话</div>
            </div>
            """, unsafe_allow_html=True)

        if st.button("📥 导出全部记忆", use_container_width=True):
            export_data = {
                "config": config,
                "memory": memory,
                "conversations": []
            }
            for f in CONVERSATIONS_DIR.glob("conv_*.json"):
                with open(f, "r", encoding="utf-8") as fp:
                    export_data["conversations"].append({
                        "file": f.name,
                        "messages": json.load(fp)
                    })
            export_str = json.dumps(export_data, ensure_ascii=False, indent=2)
            st.download_button(
                "⬇️ 下载记忆文件",
                data=export_str,
                file_name=f"panda_memory_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                use_container_width=True
            )

    st.divider()

    # --- 历史对话 ---
    with st.expander("💬 历史对话"):
        convs = get_conversation_list()
        if convs:
            for conv in convs[:20]:
                label = f"{conv['time']} · {conv['preview']}..."
                if st.button(label, key=conv["file"], use_container_width=True):
                    st.session_state.messages = load_conversation(conv["file"])
                    st.rerun()
        else:
            st.caption("暂无历史对话")

    st.divider()

    # --- 新对话 ---
    if st.button("🆕 新对话", use_container_width=True, type="primary"):
        if st.session_state.messages:
            save_conversation(st.session_state.messages)
            memory["conversations"].append({
                "time": datetime.now().isoformat(),
                "message_count": len(st.session_state.messages)
            })
            memory["total_messages"] += len(st.session_state.messages)
            save_memory(memory)
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("🐼 Panda Agent · 开源免费 · 数据本地化")
    st.caption("你的数据只属于你")

# ==================== 主界面 ====================
# 头部
st.markdown("""
<div class="panda-header">
    <h1>🐼 PANDA AGENT</h1>
    <p>开源智能助手 · 记忆持久 · 人格自定义 · 数据本地化</p>
</div>
""", unsafe_allow_html=True)

st.markdown("")

# 欢迎消息
if not st.session_state.messages:
    with st.chat_message("assistant", avatar="🐼"):
        st.markdown(f"""
**你好，我是 {config['agent_name']}。**

我能帮你做什么：

- 💬 **对话** — 有任何问题直接问我
- 🧠 **记忆** — 我会记住我们的对话，下次继续
- 🔍 **分析** — 帮你拆解方案、判断真假
- 📝 **写作** — 帮你整理思路、起草文档
- 🛡️ **守护** — 遇到可疑的东西，我会提醒你

你想聊什么？
        """)

# 显示历史消息
for msg in st.session_state.messages:
    avatar = "🐼" if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# 用户输入
if prompt := st.chat_input("跟Panda聊聊..."):
    # 检查API配置
    if not config.get("api_key"):
        st.error("⚠️ 请先在左侧「模型设置」中填写API密钥")
        st.stop()

    # 添加用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 构建完整消息列表（含系统提示）
    full_messages = [{"role": "system", "content": config["system_prompt"]}]

    # 添加长期记忆摘要（如果有）
    if memory.get("user_facts"):
        facts_text = "已知用户信息：\n" + "\n".join(
            f"- {f}" for f in memory["user_facts"][-10:]
        )
        full_messages.append({"role": "system", "content": facts_text})

    # 添加对话历史（最近20条）
    recent = st.session_state.messages[-20:]
    full_messages.extend(recent)

    # 流式输出
    with st.chat_message("assistant", avatar="🐼"):
        response = st.write_stream(chat_stream(config, full_messages))

    # 添加助手消息
    st.session_state.messages.append({"role": "assistant", "content": response})

    # 自动保存
    save_conversation(st.session_state.messages)
    memory["total_messages"] += 2
    save_memory(memory)
