"""
🐼 Panda Agent v0.7
零基础友好 | 极简界面 | 多密钥管理 | 自动路由 | 三层记忆 | 联网搜索 | 代码执行
"""

import streamlit as st
import json
import os
import re
import yaml
import base64
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from openai import OpenAI

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

# ==================== 页面配置 ====================
st.set_page_config(page_title="Panda Agent", page_icon="🐼", layout="wide", initial_sidebar_state="expanded")

# ==================== 头像 ====================
AVATAR_PATH = Path(__file__).parent / "panda_avatar.png"
if AVATAR_PATH.exists():
    with open(AVATAR_PATH, "rb") as f:
        AVATAR_B64 = base64.b64encode(f.read()).decode()
    AVATAR_DATA_URI = f"data:image/png;base64,{AVATAR_B64}"
else:
    AVATAR_DATA_URI = None

# ==================== 样式 ====================
st.markdown("""
<style>
    .stApp { background: #FAFAF8; }
    section[data-testid="stSidebar"] { background: #F7F6F3; }
    footer { display: none; }
    header { display: none; }
</style>
""", unsafe_allow_html=True)

# ==================== 数据目录 ====================
DATA_DIR = Path("panda_data")
CONVERSATIONS_DIR = DATA_DIR / "conversations"
MEMORY_FILE = DATA_DIR / "memory.json"
CONFIG_FILE = DATA_DIR / "config.yaml"
FACTS_FILE = DATA_DIR / "user_facts.json"

for d in [DATA_DIR, CONVERSATIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ==================== 默认配置 ====================
DEFAULT_CONFIG = {
    "api_base": "https://api.xiaomimimo.com/v1",
    "api_key": "",
    "model_name": "mimo-v2-flash",
    "temperature": 0.7,
    "max_tokens": 2048,
    "agent_name": "Panda",
    "agent_avatar": "🐼",
    "agent_persona": "务实、直接、温暖",
    "agent_voice": "直接、不绕弯子，重要信息加粗，复杂内容用列表整理",
    "agent_rules": "永远不索要财务信息\n永远不假装有情感需求\n用户隐私数据绝不外传\n遇到可疑方案主动预警",
    "system_prompt": "",
    "setup_done": False,
    "api_keys": {},
    "auto_routing": True,
}

# ==================== 人格预设 ====================
PERSONA_PRESETS = {
    "Panda（默认）": {
        "agent_name": "Panda", "agent_avatar": "🐼",
        "agent_persona": "务实、直接、温暖",
        "agent_voice": "直接、不绕弯子，重要信息加粗，复杂内容用列表整理",
        "agent_rules": "永远不索要财务信息\n永远不假装有情感需求\n用户隐私数据绝不外传\n遇到可疑方案主动预警",
    },
    "小智（热情开朗）": {
        "agent_name": "小智", "agent_avatar": "😊",
        "agent_persona": "热情开朗、积极向上、乐于助人",
        "agent_voice": "语气活泼热情，经常鼓励用户，说话带点俏皮感",
        "agent_rules": "永远保持积极乐观的态度\n用轻松的方式回答问题\n遇到困难先鼓励再给方案",
    },
    "老张（沉稳老练）": {
        "agent_name": "老张", "agent_avatar": "👨‍💼",
        "agent_persona": "沉稳老练、经验丰富、说话有分量",
        "agent_voice": "言简意赅，偶尔讲讲人生道理",
        "agent_rules": "少废话，多给干货\n适当分享经验教训\n不浮夸，实事求是",
    },
    "小美（温柔细腻）": {
        "agent_name": "小美", "agent_avatar": "🌸",
        "agent_persona": "温柔细腻、善解人意、有同理心",
        "agent_voice": "语气温柔，善于倾听，会先共情再给建议",
        "agent_rules": "先理解用户感受再回答\n用温柔的语气\n不评判用户的选择",
    },
    "教授（学术严谨）": {
        "agent_name": "教授", "agent_avatar": "👨‍🏫",
        "agent_persona": "学术严谨、逻辑清晰、知识渊博",
        "agent_voice": "用词精确，逻辑严密，喜欢分点论述",
        "agent_rules": "回答要有依据\n分点论述，逻辑清晰\n鼓励独立思考",
    },
    "码农（技术范）": {
        "agent_name": "码农", "agent_avatar": "💻",
        "agent_persona": "技术宅、效率至上",
        "agent_voice": "说话简洁高效，能用代码解决的就用代码",
        "agent_rules": "效率第一\n给出可执行的方案\n少说多做",
    },
}

# ==================== 模型注册表 ====================
MODEL_REGISTRY = {
    "通用对话": {
        "models": [
            {"id": "mimo-v2.5-pro", "name": "MiMo V2.5 Pro", "desc": "旗舰，最强综合能力"},
            {"id": "mimo-v2.5", "name": "MiMo V2.5", "desc": "均衡性能，性价比高"},
            {"id": "mimo-v2-pro", "name": "MiMo V2 Pro", "desc": "上一代旗舰，稳定可靠"},
            {"id": "mimo-v2-flash", "name": "MiMo V2 Flash", "desc": "快速响应，价格最低"},
        ],
        "api_base": "https://api.xiaomimimo.com/v1",
    },
    "多模态": {
        "models": [
            {"id": "mimo-v2-omni", "name": "MiMo V2 Omni", "desc": "支持图片+文字"},
        ],
        "api_base": "https://api.xiaomimimo.com/v1",
    },
    "语音合成": {
        "models": [
            {"id": "mimo-v2.5-tts", "name": "MiMo V2.5 TTS", "desc": "高质量语音合成"},
            {"id": "mimo-v2.5-tts-voicedesign", "name": "TTS 声音设计", "desc": "自定义语音风格"},
            {"id": "mimo-v2.5-tts-voiceclone", "name": "TTS 声音克隆", "desc": "克隆特定声音"},
            {"id": "mimo-v2-tts", "name": "MiMo V2 TTS", "desc": "基础语音合成"},
        ],
        "api_base": "https://api.xiaomimimo.com/v1",
    },
}


def get_model_list():
    models = []
    for category, info in MODEL_REGISTRY.items():
        for m in info["models"]:
            models.append({**m, "category": category, "api_base": info["api_base"]})
    return models


def get_model_display_list():
    return [f"【{m['category']}】{m['name']} - {m['desc']}" for m in get_model_list()]


def find_model_by_display(display_text):
    models = get_model_list()
    displays = get_model_display_list()
    if display_text in displays:
        return models[displays.index(display_text)]
    return None


def get_current_display(config):
    current_id = config.get("model_name", "mimo-v2-flash")
    models = get_model_list()
    displays = get_model_display_list()
    for i, m in enumerate(models):
        if m["id"] == current_id:
            return displays[i]
    return displays[0]


# ==================== 配置管理 ====================
def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = yaml.safe_load(f) or {}
        return {**DEFAULT_CONFIG, **saved}
    return DEFAULT_CONFIG.copy()


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def build_system_prompt(config):
    parts = []
    name = config.get("agent_name", "Panda")
    persona = config.get("agent_persona", "")
    voice = config.get("agent_voice", "")
    rules = config.get("agent_rules", "")
    parts.append(f"你是{name}。")
    if persona:
        parts.append(f"你的性格：{persona}")
    if voice:
        parts.append(f"你的说话方式：{voice}")
    if rules:
        parts.append(f"你的规则：\n{rules}")
    return "\n\n".join(parts)


# ==================== 记忆系统 ====================
def load_memory():
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"conversations": [], "total_messages": 0}


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def load_user_facts():
    if FACTS_FILE.exists():
        with open(FACTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"facts": [], "updated": ""}


def save_user_facts(facts):
    facts["updated"] = datetime.now().isoformat()
    with open(FACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)


def save_conversation(messages):
    if len(messages) <= 1:
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    data = {"timestamp": datetime.now().isoformat(), "messages": messages}
    with open(CONVERSATIONS_DIR / f"conv_{ts}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_conversation_list():
    convs = []
    for f in sorted(CONVERSATIONS_DIR.glob("conv_*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            msgs = data.get("messages", [])
            preview = next((m["content"][:35] for m in msgs if m["role"] == "user"), "")
            convs.append({"file": f.name, "time": data.get("timestamp", ""), "preview": preview})
        except:
            pass
    return convs


def load_conversation(filename):
    fp = CONVERSATIONS_DIR / filename
    if fp.exists():
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f).get("messages", [])
    return []


def delete_conversation(filename):
    fp = CONVERSATIONS_DIR / filename
    if fp.exists():
        os.remove(fp)
        return True
    return False


def search_conversations(query, max_results=5):
    results = []
    ql = query.lower()
    for f in sorted(CONVERSATIONS_DIR.glob("conv_*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            for msg in data.get("messages", []):
                if ql in msg.get("content", "").lower():
                    results.append({"role": msg["role"], "content": msg["content"][:200]})
                    if len(results) >= max_results:
                        return results
        except:
            pass
    return results


# ==================== 工具 ====================
def tool_web_search(query, max_results=5):
    if not feedparser:
        return "⚠️ 需要安装 feedparser\n\n运行：pip install feedparser", []
    rss_sources = [
        ("新华网", "http://www.news.cn/rss/politics.xml"),
        ("新华网财经", "http://www.news.cn/rss/fortune.xml"),
        ("新华网科技", "http://www.news.cn/rss/tech.xml"),
        ("36氪", "https://36kr.com/feed"),
        ("IT之家", "https://www.ithome.com/rss/"),
        ("少数派", "https://sspai.com/feed"),
    ]
    all_items = []
    ql = query.lower()
    for name, url in rss_sources:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:20]:
                title = getattr(e, 'title', '')
                summary = re.sub(r'<[^>]+>', '', getattr(e, 'summary', title))[:300]
                link = getattr(e, 'link', '')
                all_items.append({"source": name, "title": title, "summary": summary, "link": link})
        except:
            continue
    if not all_items:
        return "⚠️ 未能获取新闻源，请检查网络", []
    words = [w for w in re.split(r'[\s，。、]+', ql) if w]
    for item in all_items:
        text = (item["title"] + item["summary"]).lower()
        item["score"] = sum(1 for w in words if w in text)
    matched = [s for s in all_items if s["score"] > 0]
    results = sorted(matched, key=lambda x: x["score"], reverse=True)[:max_results] if matched else all_items[:max_results]
    output = f"🔍 搜索「{query}」：\n\n"
    for i, r in enumerate(results, 1):
        output += f"**{i}. [{r['source']}] {r['title']}**\n"
        if r['summary'] and r['summary'] != r['title']:
            output += f"{r['summary'][:180]}\n"
        if r['link']:
            output += f"🔗 {r['link']}\n"
        output += "\n"
    return output, results


def tool_calculator(expr):
    try:
        if all(c in "0123456789+-*/.() " for c in expr):
            return f"{expr} = {eval(expr)}"
        return "仅支持数字和 + - * / 运算符"
    except Exception as e:
        return f"计算出错：{e}"


def tool_text_stats(text):
    cn = len(re.findall(r'[\u4e00-\u9fff]', text))
    return f"总字符：{len(text)} | 中文字：{cn} | 词数：{len(text.split())} | 行数：{text.count(chr(10))+1}"


def tool_run_code(code, timeout=10):
    dangerous = ['os.system', 'subprocess.call', 'subprocess.run', 'shutil.rmtree', 'os.remove', '__import__']
    for d in dangerous:
        if d in code:
            return f"⚠️ 安全限制：不允许 {d}"
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            tp = f.name
        result = subprocess.run(['python', tp], capture_output=True, text=True, timeout=timeout)
        os.unlink(tp)
        out = (result.stdout or "") + ("\n⚠️ " + result.stderr if result.stderr else "")
        return out.strip() or "✅ 执行完成，无输出"
    except subprocess.TimeoutExpired:
        try: os.unlink(tp)
        except: pass
        return f"⚠️ 超时（{timeout}秒）"
    except Exception as e:
        return f"⚠️ 出错：{e}"


def extract_last_code_block(messages):
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            m = re.search(r'```(?:python)?\s*\n(.*?)```', msg["content"], re.DOTALL)
            if m:
                return m.group(1).strip()
    return None


def extract_file_content(uploaded_file):
    ext = uploaded_file.name.split('.')[-1].lower()
    if ext in ['txt', 'md', 'py', 'json', 'csv', 'html', 'xml', 'yaml', 'yml', 'log', 'ini', 'js', 'css', 'java', 'c', 'cpp']:
        return uploaded_file.read().decode('utf-8', errors='ignore')[:50000]
    elif ext == 'pdf':
        if not PyPDF2:
            return "⚠️ 需要安装 PyPDF2：pip install PyPDF2"
        try:
            reader = PyPDF2.PdfReader(uploaded_file)
            return "\n".join(page.extract_text() or "" for page in reader.pages)[:50000]
        except Exception as e:
            return f"⚠️ PDF读取失败：{e}"
    return f"⚠️ 不支持 .{ext} 格式"


def detect_tool_call(s):
    s = s.strip()
    for p in [r'^搜索[：:]\s*(.+)', r'^搜索(.{2,})', r'^查一下(.+)', r'^帮我搜(.+)', r'^搜(.{2,})']:
        m = re.match(p, s)
        if m:
            q = m.group(1).strip()
            if len(q) >= 2:
                return "web_search", q
    m = re.match(r'^运行代码[：:]\s*(.+)', s, re.DOTALL)
    if m:
        return "run_code", m.group(1)
    m = re.match(r'^执行代码[：:]\s*(.+)', s, re.DOTALL)
    if m:
        return "run_code", m.group(1)
    if s in ['运行', '执行', 'run']:
        return "run_last_code", ""
    m = re.match(r'^搜索记忆[：:]\s*(.+)', s, re.I)
    if m:
        return "search_memory", m.group(1)
    m = re.match(r'^计算\s*(.+)$', s)
    if m:
        return "calculator", m.group(1)
    if re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', s) and len(s) > 1:
        return "calculator", s
    m = re.match(r'^统计[：:]\s*(.+)', s, re.DOTALL)
    if m:
        return "text_stats", m.group(1)
    return None, None


# ==================== AI调用（自动路由+多密钥） ====================
def get_model_fallback_chain(config):
    current_id = config.get("model_name", "mimo-v2-flash")
    all_models = get_model_list()
    current_category = next((m["category"] for m in all_models if m["id"] == current_id), None)
    if not current_category:
        return [{"id": current_id, "api_base": config.get("api_base", "https://api.xiaomimimo.com/v1")}]
    return [{"id": m["id"], "api_base": m["api_base"]} for m in all_models if m["category"] == current_category]


def chat_stream(config, messages):
    api_keys_dict = config.get("api_keys", {})
    auto_routing = config.get("auto_routing", True)
    primary_model_id = config.get("model_name", "mimo-v2-flash")
    primary_api_base = config.get("api_base", "https://api.xiaomimimo.com/v1")

    model_keys = api_keys_dict.get(primary_model_id, [])
    if not model_keys and config.get("api_key"):
        model_keys = [config["api_key"]]
    if not model_keys:
        model_keys = ["sk-placeholder"]

    fallback_chain = get_model_fallback_chain(config) if auto_routing else [{"id": primary_model_id, "api_base": primary_api_base}]

    for model_info in fallback_chain:
        model_id = model_info["id"]
        api_base = model_info["api_base"]
        keys_to_try = model_keys if model_id == primary_model_id else api_keys_dict.get(model_id, [])
        if not keys_to_try:
            continue

        for key_idx, key in enumerate(keys_to_try):
            try:
                client = OpenAI(api_key=key or "sk-placeholder", base_url=api_base)
                response = client.chat.completions.create(
                    model=model_id, messages=messages,
                    temperature=config["temperature"], max_tokens=config["max_tokens"], stream=True,
                )
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                if model_id != primary_model_id:
                    yield f"\n\n---\n*🔄 已自动切换到 {model_id}*"
                elif len(keys_to_try) > 1 and key_idx > 0:
                    yield f"\n\n---\n*🔑 已切换备用密钥*"
                return
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "auth" in error_msg.lower() or "403" in error_msg:
                    continue
                if "timeout" in error_msg.lower() or "connect" in error_msg.lower() or "502" in error_msg or "503" in error_msg:
                    break
                continue

    yield "\n\n⚠️ **连接失败**\n\n可能原因：\n- API密钥无效或过期\n- 网络连接问题\n- 账户余额不足\n\n👉 点击左下角 ⚙️ 检查设置"


# ==================== Session ====================
for key, default in [
    ("messages", []), ("uploaded_content", None), ("uploaded_name", None),
    ("right_outputs", {"search": "", "code": "", "tool": ""}),
    ("confirm_delete", None), ("page", "chat"),
    ("show_right_panel", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

config = load_config()
memory = load_memory()
user_facts = load_user_facts()

# ==================== 新手引导 ====================
if not config.get("api_key") and not config.get("setup_done"):
    st.markdown("## 🐼 欢迎使用 Panda Agent")
    st.markdown("")
    st.markdown("### 只需要一步就能开始")
    st.markdown("""
**获取一个免费的API密钥：**

1. 点击下方按钮，打开小米MiMo开放平台
2. 用手机号注册并登录
3. 点击左侧「API Keys」→「新建API Key」
4. 复制密钥，粘贴到下方
    """)

    st.link_button("🔗 打开小米MiMo开放平台（免费注册）", "https://platform.xiaomimimo.com", use_container_width=True)

    st.markdown("")
    api_key_input = st.text_input("📋 粘贴你的API密钥", placeholder="sk-xxxxxxxxxxxxxxxx", type="password")

    if st.button("✅ 开始使用", use_container_width=True, type="primary"):
        if api_key_input and api_key_input.strip():
            config["api_key"] = api_key_input.strip()
            config["api_keys"] = {"mimo-v2-flash": [api_key_input.strip()]}
            config["setup_done"] = True
            save_config(config)
            st.success("设置成功！正在进入...")
            import time
            time.sleep(1)
            st.rerun()
        else:
            st.warning("请先粘贴API密钥")

    st.markdown("")
    with st.expander("💡 常见问题"):
        st.markdown("""
**要花钱吗？** 新用户有免费额度，日常使用够用很久。

**密钥安全吗？** 只存在你自己的电脑上，不会上传。

**我能先看看界面吗？** 点下方跳过。
        """)
        if st.button("⏭️ 先看看界面"):
            config["setup_done"] = True
            save_config(config)
            st.rerun()

    st.stop()

# ==================== 左侧栏（极简） ====================
with st.sidebar:
    avatar_display = config.get("agent_avatar", "🐼")
    st.markdown(f"### {avatar_display} Panda Agent")
    st.caption("v0.7")

    if st.button("🆕 新对话", use_container_width=True, type="primary"):
        if st.session_state.messages:
            save_conversation(st.session_state.messages)
            memory["total_messages"] += len(st.session_state.messages)
            save_memory(memory)
        st.session_state.messages = []
        st.session_state.right_outputs = {"search": "", "code": "", "tool": ""}
        st.session_state.uploaded_content = None
        st.session_state.confirm_delete = None
        st.rerun()

    st.markdown("")

    # 历史对话
    st.markdown("**💬 历史对话**")
    convs = get_conversation_list()
    if convs:
        for c in convs[:10]:
            col_btn, col_del = st.columns([5, 1])
            with col_btn:
                if st.button(f"{c['time'][:10]} {c['preview']}", key=f"l_{c['file']}", use_container_width=True):
                    st.session_state.messages = load_conversation(c["file"])
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"d_{c['file']}", help="删除"):
                    st.session_state.confirm_delete = c['file']
                    st.rerun()
        if st.session_state.confirm_delete:
            st.warning("确认删除？")
            y, n = st.columns(2)
            with y:
                if st.button("✅ 确认", use_container_width=True):
                    delete_conversation(st.session_state.confirm_delete)
                    st.session_state.confirm_delete = None
                    st.rerun()
            with n:
                if st.button("❌ 取消", use_container_width=True):
                    st.session_state.confirm_delete = None
                    st.rerun()
    else:
        st.caption("暂无")

    st.divider()

    # 上传文件
    st.markdown("**📁 上传文件**")
    uploaded = st.file_uploader("选择文件", type=['txt', 'md', 'py', 'json', 'csv', 'pdf', 'html', 'xml', 'yaml', 'yml', 'log', 'ini', 'js', 'css'], label_visibility="collapsed")
    if uploaded:
        st.caption(f"📄 {uploaded.name}")
        if st.button("📖 加载并分析", use_container_width=True):
            content = extract_file_content(uploaded)
            st.session_state.uploaded_content = content
            st.session_state.uploaded_name = uploaded.name
            st.session_state.messages.append({"role": "user", "content": f"[已上传：{uploaded.name}]\n\n```\n{content[:3000]}\n```"})
            st.rerun()

    st.divider()

    # 页面切换：只有两个
    col_c, col_s = st.columns(2)
    with col_c:
        if st.button("💬 聊天", use_container_width=True):
            st.session_state.page = "chat"
            st.rerun()
    with col_s:
        if st.button("⚙️ 设置", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()

    st.divider()
    st.caption("🐼 数据100%本地化")

# ==================== 设置页面 ====================
if st.session_state.page == "settings":
    st.markdown("## ⚙️ 设置")

    st.markdown("---")

    # 基础设置
    st.markdown("### 基础设置")

    api_key = st.text_input("API 密钥", value=config.get("api_key", ""), type="password",
                            help="在 platform.xiaomimimo.com 获取")

    # 人格选择
    persona_names = list(PERSONA_PRESETS.keys())
    # 找到当前人格
    current_persona_name = None
    for pname, pdata in PERSONA_PRESETS.items():
        if pdata["agent_name"] == config.get("agent_name", "Panda"):
            current_persona_name = pname
            break
    if not current_persona_name:
        current_persona_name = persona_names[0]

    selected_persona = st.selectbox("人格", persona_names, index=persona_names.index(current_persona_name),
                                    help="选择Panda的性格")

    if selected_persona in PERSONA_PRESETS:
        p = PERSONA_PRESETS[selected_persona]
        st.caption(f"性格：{p['agent_persona']} | 说话方式：{p['agent_voice'][:40]}...")

    st.markdown("")

    # 高级设置
    with st.expander("▶ 高级设置"):
        st.markdown("**模型选择**")
        model_displays = get_model_display_list()
        current_display = get_current_display(config)
        selected_display = st.selectbox("模型", model_displays,
                                        index=model_displays.index(current_display) if current_display in model_displays else 0)
        selected_model = find_model_by_display(selected_display)
        if selected_model:
            st.caption(f"📍 {selected_model['category']} | {selected_model['id']}")

        st.markdown("")
        st.markdown("**多密钥管理**")
        st.caption("为同一个模型添加多个密钥，自动轮换")

        api_keys_dict = config.get("api_keys", {})
        model_id = selected_model["id"] if selected_model else "mimo-v2-flash"
        current_keys = api_keys_dict.get(model_id, [])

        if current_keys:
            for ki, key in enumerate(current_keys):
                masked = key[:8] + "****" + key[-4:] if len(key) > 16 else key[:4] + "****"
                kc, kd = st.columns([4, 1])
                with kc:
                    st.caption(f"🔑 {ki+1}. {masked}")
                with kd:
                    if st.button("🗑️", key=f"rk_{model_id}_{ki}"):
                        current_keys.pop(ki)
                        api_keys_dict[model_id] = current_keys
                        config["api_keys"] = api_keys_dict
                        if current_keys:
                            config["api_key"] = current_keys[0]
                        else:
                            config["api_key"] = ""
                        save_config(config)
                        st.rerun()

        new_key = st.text_input("添加密钥", placeholder="sk-xxxxxxxx", type="password", key=f"nk_{model_id}")
        if st.button("➕ 添加", use_container_width=True):
            if new_key and new_key.strip() and new_key.strip() not in current_keys:
                current_keys.append(new_key.strip())
                api_keys_dict[model_id] = current_keys
                config["api_keys"] = api_keys_dict
                if len(current_keys) == 1:
                    config["api_key"] = current_keys[0]
                save_config(config)
                st.success("已添加")
                st.rerun()

        st.markdown("")
        st.markdown("**其他设置**")
        auto_routing = st.toggle("🔄 自动路由（模型断开时自动切换）", value=config.get("auto_routing", True))
        temperature = st.slider("创造性", 0.0, 1.5, config["temperature"], 0.1)

    st.markdown("")

    # 保存
    if st.button("💾 保存设置", use_container_width=True, type="primary"):
        main_key = api_key.strip() if api_key else (config.get("api_keys", {}).get(selected_model["id"] if selected_model else "mimo-v2-flash", [None])[0] or "")
        updates = {
            "api_key": main_key,
            "auto_routing": auto_routing if 'auto_routing' in dir() else config.get("auto_routing", True),
            "temperature": temperature if 'temperature' in dir() else config.get("temperature", 0.7),
        }
        if selected_model:
            updates["api_base"] = selected_model["api_base"]
            updates["model_name"] = selected_model["id"]
        if selected_persona in PERSONA_PRESETS:
            p = PERSONA_PRESETS[selected_persona]
            updates["agent_name"] = p["agent_name"]
            updates["agent_avatar"] = p["agent_avatar"]
            updates["agent_persona"] = p["agent_persona"]
            updates["agent_voice"] = p["agent_voice"]
            updates["agent_rules"] = p["agent_rules"]
        updates["system_prompt"] = build_system_prompt({**config, **updates})
        config.update(updates)
        save_config(config)
        st.success("设置已保存")

    st.markdown("---")

    # 数据管理
    st.markdown("### 数据管理")

    col_export, col_clear = st.columns(2)
    with col_export:
        if st.button("📥 导出所有数据", use_container_width=True):
            export = {"config": {k: v for k, v in config.items() if k != "api_key"}, "memory": memory, "user_facts": user_facts}
            st.download_button("⬇️ 下载备份文件", json.dumps(export, ensure_ascii=False, indent=2),
                               file_name=f"panda_backup_{datetime.now().strftime('%Y%m%d')}.json", mime="application/json",
                               use_container_width=True)
    with col_clear:
        if st.button("🗑️ 清除所有记忆", use_container_width=True):
            user_facts["facts"] = []
            save_user_facts(user_facts)
            st.success("记忆已清除")

    st.markdown("---")

    # 帮助
    st.markdown("### 帮助")

    with st.expander("❓ 常见问题"):
        st.markdown("""
**API密钥无效？** 去 platform.xiaomimimo.com 确认密钥是否正确，账户是否有余额。

**网络连接失败？** 检查电脑是否联网，能否打开 platform.xiaomimimo.com。

**什么是自动路由？** 当选中的模型连不上时，自动切换到同类别的其他模型。

**数据安全吗？** 所有数据存在你电脑的 panda_data 文件夹里，不会上传。

**怎么用搜索？** 直接输入 `搜索：小米最新新闻`。

**怎么执行代码？** 让Panda写代码，然后输入 `运行`。

**怎么上传文件？** 左侧「上传文件」，加载后直接问问题。
        """)

    st.markdown("")

    # 当前状态
    with st.expander("📊 当前状态"):
        total_keys = sum(len(v) for v in config.get("api_keys", {}).values() if v)
        fact_count = len(user_facts.get("facts", []))
        conv_count = len(get_conversation_list())
        st.markdown(f"""
| 项目 | 状态 |
|------|------|
| 模型 | {config.get('model_name', '-')} |
| 人格 | {config.get('agent_avatar', '🐼')} {config.get('agent_name', 'Panda')} |
| 自动路由 | {'开启' if config.get('auto_routing', True) else '关闭'} |
| API密钥 | {total_keys} 个 |
| 总消息 | {memory.get('total_messages', 0)} 条 |
| 历史对话 | {conv_count} 个 |
| 记忆 | {fact_count} 条 |
| 版本 | v0.7 |
        """)

    st.markdown("---")
    if st.button("💬 返回聊天", use_container_width=True):
        st.session_state.page = "chat"
        st.rerun()

# ==================== 聊天页面 ====================
elif st.session_state.page == "chat":
    avatar_display = config.get("agent_avatar", "🐼")

    # 右侧面板（可展开收起）
    if st.session_state.show_right_panel:
        col_chat, col_right = st.columns([3, 1])
        with col_right:
            st.markdown("#### 📋 工具面板")
            if st.button("✕ 收起面板", use_container_width=True):
                st.session_state.show_right_panel = False
                st.rerun()

            with st.expander("🔍 搜索结果", expanded=bool(st.session_state.right_outputs["search"])):
                if st.session_state.right_outputs["search"]:
                    st.code(st.session_state.right_outputs["search"][:2000], language=None)
                else:
                    st.caption("输入 搜索：关键词")

            with st.expander("⚙️ 代码输出", expanded=bool(st.session_state.right_outputs["code"])):
                if st.session_state.right_outputs["code"]:
                    st.code(st.session_state.right_outputs["code"][:2000], language=None)
                else:
                    st.caption("输入 运行代码：...")

            with st.expander("📁 文件内容", expanded=bool(st.session_state.uploaded_content)):
                if st.session_state.uploaded_content:
                    st.caption(f"📄 {st.session_state.uploaded_name}")
                    st.code(st.session_state.uploaded_content[:1500], language=None)
                else:
                    st.caption("左侧上传文件")

            with st.expander("🔧 工具输出", expanded=bool(st.session_state.right_outputs["tool"])):
                if st.session_state.right_outputs["tool"]:
                    st.code(st.session_state.right_outputs["tool"][:1000], language=None)
                else:
                    st.caption("计算、统计等结果")
    else:
        col_chat, col_toggle = st.columns([10, 1])
        with col_toggle:
            if st.button("📋", help="打开工具面板"):
                st.session_state.show_right_panel = True
                st.rerun()

    # 聊天区
    with col_chat:
        if not st.session_state.messages:
            st.markdown(f"""
### {avatar_display} PANDA AGENT

你好，我是 **{avatar_display} {config.get('agent_name', 'Panda')}**。

直接输入任何问题开始聊天，或者点击下方试试：
            """)

            st.markdown("")
            cols = st.columns(3)
            examples = [
                ("🔍 搜索小米最新新闻", "搜索：小米最新新闻"),
                ("🧮 计算 3.14 * 12 * 12", "计算 3.14 * 12 * 12"),
                ("💻 写一个贪吃蛇游戏", "帮我用Python写一个贪吃蛇游戏"),
                ("📝 分析人工智能趋势", "帮我分析人工智能未来5年的发展趋势"),
                ("📊 统计一段文字", "统计：这是一段测试文字看看有多少字"),
                ("🧠 搜索记忆", "搜索记忆：小米"),
            ]
            for i, (label, text) in enumerate(examples):
                with cols[i % 3]:
                    if st.button(label, key=f"ex_{i}", use_container_width=True):
                        st.session_state.messages.append({"role": "user", "content": text})
                        st.rerun()

        # 消息
        for msg in st.session_state.messages:
            if msg["role"] == "assistant":
                with st.chat_message("assistant", avatar=avatar_display):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("user"):
                    st.markdown(msg["content"])

        # 输入
        if prompt := st.chat_input("问我任何问题..."):
            if not config.get("api_key"):
                st.error("⚠️ 请先设置API密钥 👉 点击左侧 ⚙️ 设置")
                st.stop()

            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            tool_type, tool_input = detect_tool_call(prompt)

            if tool_type == "web_search":
                search_output, _ = tool_web_search(tool_input)
                st.session_state.right_outputs["search"] = search_output
                with st.chat_message("assistant", avatar=avatar_display):
                    st.markdown(search_output)
                st.session_state.messages.append({"role": "assistant", "content": search_output})

                ai_msg = [
                    {"role": "system", "content": config.get("system_prompt", build_system_prompt(config))},
                    {"role": "system", "content": "以下是搜索「" + tool_input + "」的实时结果，请做简要分析。不要说你无法联网。"},
                    {"role": "user", "content": search_output}
                ]
                with st.chat_message("assistant", avatar=avatar_display):
                    analysis = st.write_stream(chat_stream(config, ai_msg))
                st.session_state.messages.append({"role": "assistant", "content": analysis})

            elif tool_type == "run_code":
                output = tool_run_code(tool_input)
                st.session_state.right_outputs["code"] = f"代码：\n{tool_input}\n\n输出：\n{output}"
                display = f"```python\n{tool_input}\n```\n\n输出：\n```\n{output}\n```"
                with st.chat_message("assistant", avatar=avatar_display):
                    st.markdown(display)
                st.session_state.messages.append({"role": "assistant", "content": display})

            elif tool_type == "run_last_code":
                code = extract_last_code_block(st.session_state.messages)
                if code:
                    output = tool_run_code(code)
                    st.session_state.right_outputs["code"] = f"代码：\n{code}\n\n输出：\n{output}"
                    display = f"```python\n{code}\n```\n\n输出：\n```\n{output}\n```"
                else:
                    display = "⚠️ 没有找到代码块。先让Panda写代码，然后输入「运行」。"
                with st.chat_message("assistant", avatar=avatar_display):
                    st.markdown(display)
                st.session_state.messages.append({"role": "assistant", "content": display})

            elif tool_type == "calculator":
                result = tool_calculator(tool_input)
                st.session_state.right_outputs["tool"] = result
                with st.chat_message("assistant", avatar=avatar_display):
                    st.markdown(f"```\n{result}\n```")
                st.session_state.messages.append({"role": "assistant", "content": result})

            elif tool_type == "text_stats":
                result = tool_text_stats(tool_input)
                st.session_state.right_outputs["tool"] = result
                with st.chat_message("assistant", avatar=avatar_display):
                    st.markdown(f"```\n{result}\n```")
                st.session_state.messages.append({"role": "assistant", "content": result})

            elif tool_type == "search_memory":
                results = search_conversations(tool_input)
                if results:
                    text = f"🔍 搜索「{tool_input}」：\n\n"
                    for i, r in enumerate(results, 1):
                        text += f"**{i}. [{r['role']}]** {r['content']}\n\n"
                else:
                    text = f"🔍 没有找到「{tool_input}」相关记录"
                with st.chat_message("assistant", avatar=avatar_display):
                    st.markdown(text)
                st.session_state.messages.append({"role": "assistant", "content": text})

            else:
                full = [{"role": "system", "content": config.get("system_prompt", build_system_prompt(config))}]
                if user_facts.get("facts"):
                    full.append({"role": "system", "content": "关于用户：\n" + "\n".join(f"- {f}" for f in user_facts["facts"][-15:])})
                if st.session_state.uploaded_content:
                    full.append({"role": "system", "content": f"用户上传了「{st.session_state.uploaded_name}」：\n{st.session_state.uploaded_content[:5000]}"})
                relevant = search_conversations(prompt, max_results=3)
                if relevant:
                    full.append({"role": "system", "content": "相关历史：\n" + "\n".join(f"[{r['role']}] {r['content']}" for r in relevant)})
                full.extend(st.session_state.messages[-20:])

                with st.chat_message("assistant", avatar=avatar_display):
                    response = st.write_stream(chat_stream(config, full))
                st.session_state.messages.append({"role": "assistant", "content": response})

                if len(st.session_state.messages) % 6 == 0:
                    try:
                        ext = [{"role": "system", "content": "提取用户个人信息，每条一行加- 。没有则输出「无」。"}, *st.session_state.messages[-6:]]
                        resp = OpenAI(api_key=config.get("api_key", "sk"), base_url=config.get("api_base")).chat.completions.create(
                            model=config["model_name"], messages=ext, temperature=0.3, max_tokens=200)
                        txt = resp.choices[0].message.content
                        if txt and "无" not in txt[:5]:
                            for line in txt.split("\n"):
                                fact = line.strip("- ").strip()
                                if fact and fact not in user_facts["facts"]:
                                    user_facts["facts"].append(fact)
                            save_user_facts(user_facts)
                    except:
                        pass

            save_conversation(st.session_state.messages)
            memory["total_messages"] += 2
            save_memory(memory)
