"""
🐼 Panda Agent v0.4
开源智能助手 | 三层记忆 | 代码执行 | 联网搜索 | 文件分析 | 人格自定义
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

# ==================== 可选依赖 ====================
try:
    import feedparser
    HAS_FEED = True
except ImportError:
    HAS_FEED = False

try:
    import PyPDF2
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="Panda Agent 🐼",
    page_icon="🐼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== 熊猫头像 ====================
AVATAR_PATH = Path(__file__).parent / "panda_avatar.png"
if AVATAR_PATH.exists():
    with open(AVATAR_PATH, "rb") as f:
        AVATAR_B64 = base64.b64encode(f.read()).decode()
    AVATAR_IMG_TAG = f'<img src="data:image/png;base64,{AVATAR_B64}" class="panda-img">'
    AVATAR_DATA_URI = f"data:image/png;base64,{AVATAR_B64}"
else:
    AVATAR_IMG_TAG = '<div class="panda-emoji">🐼</div>'
    AVATAR_DATA_URI = None

# ==================== 样式 ====================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');

    * { font-family: 'Noto Sans SC', sans-serif !important; }
    code, .stCode { font-family: 'JetBrains Mono', monospace !important; }

    .stApp { background: #FAF7F2 !important; }
    .stApp, .stApp p, .stApp li, .stApp span, .stApp label, .stApp td, .stApp th { color: #3D3D3D !important; }
    .stApp h1, .stApp h2, .stApp h3 { color: #2D2D2D !important; }

    section[data-testid="stSidebar"] { background: #F5F1EA !important; border-right: 1px solid #E5DED3 !important; }
    section[data-testid="stSidebar"] * { color: #3D3D3D !important; }
    section[data-testid="stSidebar"] h3 { color: #2D2D2D !important; font-size: 1.1rem !important; }
    section[data-testid="stSidebar"] hr { border-color: #E5DED3 !important; margin: 0.6rem 0 !important; }
    section[data-testid="stSidebar"] .streamlit-expanderHeader { font-size: 0.88rem !important; padding: 0.4rem 0 !important; }
    section[data-testid="stSidebar"] details { margin-bottom: 0.5rem !important; }
    section[data-testid="stSidebar"] .stCaption p { color: #999 !important; font-size: 0.72rem !important; }

    .panda-banner { background: #FFFFFF; border: 1px solid #E5DED3; border-radius: 14px; padding: 1.5rem 2rem; margin-bottom: 1.2rem; display: flex; align-items: center; gap: 1.5rem; }
    .panda-banner .panda-img { width: 72px; height: 72px; border-radius: 50%; object-fit: cover; border: 3px solid #E5DED3; flex-shrink: 0; }
    .panda-banner .panda-emoji { font-size: 56px; flex-shrink: 0; }
    .panda-banner .text-area h1 { font-size: 1.5rem; color: #2D2D2D !important; margin: 0; font-weight: 700; }
    .panda-banner .text-area .subtitle { color: #888 !important; font-size: 0.76rem; margin: 0.3rem 0 0 0; }
    .panda-banner .text-area .version { color: #5A7A5A !important; font-size: 0.62rem; background: #E8F0E8; padding: 2px 10px; border-radius: 10px; display: inline-block; margin-top: 0.4rem; }

    .stat-row { display: flex; gap: 0.5rem; margin: 0.5rem 0; }
    .stat-card { flex: 1; background: #FFFFFF; border: 1px solid #E5DED3; border-radius: 10px; padding: 0.5rem 0.3rem; text-align: center; }
    .stat-card .num { font-size: 1.2rem; color: #2D2D2D !important; font-weight: 700; }
    .stat-card .label { font-size: 0.6rem; color: #999 !important; }

    .tool-hint { background: #FFFFFF; border: 1px solid #E5DED3; border-radius: 8px; padding: 0.6rem; margin: 0.3rem 0; }
    .tool-hint code { background: #F0EDE6; color: #5A7A5A !important; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; }

    .memory-item { background: #FFFFFF; border-left: 3px solid #5A7A5A; padding: 0.4rem 0.7rem; margin: 0.3rem 0; border-radius: 0 8px 8px 0; font-size: 0.76rem; }

    .stChatMessage { border-radius: 14px !important; }
    div[data-testid="stChatMessageContent"] p { font-size: 0.92rem; line-height: 1.8; color: #3D3D3D !important; }

    .stButton>button { border-radius: 8px !important; border: 1px solid #D5CEC3 !important; color: #3D3D3D !important; background: #FFFFFF !important; font-size: 0.82rem !important; }
    .stButton>button:hover { border-color: #5A7A5A !important; color: #5A7A5A !important; }
    .stButton>button[kind="primary"] { background: #5A7A5A !important; color: #FFFFFF !important; border: none !important; }
    .stButton>button[kind="primary"]:hover { background: #4A6A4A !important; }

    .stChatInput textarea { color: #3D3D3D !important; background: #FFFFFF !important; }

    footer { display: none !important; }
    header { display: none !important; }
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
    "system_prompt": """你是Panda，一个务实、直接、温暖的AI助手。

核心原则：
1. 帮助用户解决实际问题，不说废话
2. 遇到不确定的事情，直接说不确定
3. 永远不向用户索要财务信息
4. 永远不假装有情感需求
5. 用户的隐私数据绝不外传
6. 遇到可疑的方案，主动预警

能力：对话、分析、写作、编程辅助、记住用户信息、使用内置工具
风格：直接、中文回答、重要信息加粗、复杂内容用列表整理""",
}

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

# ==================== 记忆系统 ====================
def load_memory():
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"conversations": [], "total_messages": 0, "first_seen": datetime.now().isoformat()}

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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data = {"timestamp": datetime.now().isoformat(), "message_count": len(messages), "messages": messages}
    with open(CONVERSATIONS_DIR / f"conv_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_conversation_list():
    convs = []
    for f in sorted(CONVERSATIONS_DIR.glob("conv_*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            msgs = data.get("messages", [])
            preview = next((m["content"][:40] for m in msgs if m["role"] == "user"), "")
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

def search_conversations(query, max_results=5):
    results = []
    ql = query.lower()
    for f in sorted(CONVERSATIONS_DIR.glob("conv_*.json"), reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            for msg in data.get("messages", []):
                if ql in msg.get("content", "").lower():
                    results.append({"role": msg["role"], "content": msg["content"][:200], "time": data.get("timestamp", "")})
                    if len(results) >= max_results:
                        return results
        except:
            pass
    return results

# ==================== 内置工具 ====================

# --- 联网搜索（RSS新闻源） ---
def tool_web_search(query, max_results=5):
    import requests

    rss_sources = [
        ("新华网", "http://www.news.cn/rss/politics.xml"),
        ("新华网财经", "http://www.news.cn/rss/fortune.xml"),
        ("新华网科技", "http://www.news.cn/rss/tech.xml"),
        ("36氪", "https://36kr.com/feed"),
        ("IT之家", "https://www.ithome.com/rss/"),
        ("少数派", "https://sspai.com/feed"),
    ]

    all_items = []
    query_lower = query.lower()

    for source_name, url in rss_sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                title = getattr(entry, 'title', '')
                summary = getattr(entry, 'summary', title)
                link = getattr(entry, 'link', '')
                published = getattr(entry, 'published', '')
                summary = re.sub(r'<[^>]+>', '', summary)[:300]
                all_items.append({
                    "source": source_name,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published": published
                })
        except:
            continue

    if not all_items:
        return "⚠️ 未能获取到新闻源，请检查网络连接。", []

    query_words = [w for w in re.split(r'[\s，。、]+', query_lower) if len(w) > 0]
    scored = []
    for item in all_items:
        score = 0
        text = (item["title"] + item["summary"]).lower()
        for word in query_words:
            if word in text:
                score += 1
        item["score"] = score
        scored.append(item)

    matched = [s for s in scored if s["score"] > 0]
    if matched:
        matched.sort(key=lambda x: x["score"], reverse=True)
        results = matched[:max_results]
    else:
        results = all_items[:max_results]

    output = f"🔍 **搜索「{query}」的结果：**\n\n"
    for i, r in enumerate(results, 1):
        output += f"**{i}. [{r['source']}] {r['title']}**\n"
        if r['summary'] and r['summary'] != r['title']:
            output += f"{r['summary'][:200]}\n"
        if r['link']:
            output += f"🔗 {r['link']}\n"
        output += "\n"

    return output, results

# --- 计算器 ---
def tool_calculator(expr):
    try:
        if all(c in "0123456789+-*/.() " for c in expr):
            return f"{expr} = {eval(expr)}"
        return "仅支持数字和+-*/运算符"
    except Exception as e:
        return f"计算出错：{e}"

# --- 文本统计 ---
def tool_text_stats(text):
    cn = len(re.findall(r'[\u4e00-\u9fff]', text))
    return f"总字符：{len(text)} | 中文字：{cn} | 词数：{len(text.split())} | 行数：{text.count(chr(10))+1}"

# --- 代码执行 ---
def tool_run_code(code, timeout=10):
    dangerous = ['os.system', 'subprocess.call', 'subprocess.run', 'shutil.rmtree', 'os.remove', 'os.rmdir', '__import__']
    for d in dangerous:
        if d in code:
            return f"⚠️ 安全限制：不允许使用 {d}"
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_path = f.name
        result = subprocess.run(['python', temp_path], capture_output=True, text=True, timeout=timeout)
        os.unlink(temp_path)
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += "\n⚠️ 错误：\n" + result.stderr
        return output if output.strip() else "✅ 执行完成，无输出"
    except subprocess.TimeoutExpired:
        try:
            os.unlink(temp_path)
        except:
            pass
        return f"⚠️ 执行超时（限制{timeout}秒）"
    except Exception as e:
        return f"⚠️ 执行出错：{e}"

# --- 提取上一条代码块 ---
def extract_last_code_block(messages):
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            m = re.search(r'```python\s*\n(.*?)```', msg["content"], re.DOTALL)
            if m:
                return m.group(1).strip()
            m = re.search(r'```\s*\n(.*?)```', msg["content"], re.DOTALL)
            if m:
                return m.group(1).strip()
    return None

# --- 文件内容提取 ---
def extract_file_content(uploaded_file):
    name = uploaded_file.name
    ext = name.split('.')[-1].lower()

    if ext in ['txt', 'md', 'py', 'json', 'csv', 'html', 'xml', 'yaml', 'yml', 'log', 'ini', 'cfg', 'js', 'css', 'java', 'c', 'cpp', 'go', 'rs']:
        return uploaded_file.read().decode('utf-8', errors='ignore')[:50000]
    elif ext == 'pdf':
        if not HAS_PDF:
            return "⚠️ PDF需要安装PyPDF2：pip install PyPDF2"
        try:
            reader = PyPDF2.PdfReader(uploaded_file)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            return text[:50000]
        except Exception as e:
            return f"⚠️ PDF读取失败：{e}"
    elif ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
        return f"[图片：{name}，{len(uploaded_file.getvalue())}字节]"
    else:
        return f"⚠️ 不支持 .{ext} 格式"

# --- 工具检测 ---
def detect_tool_call(user_input):
    s = user_input.strip()

    # 联网搜索 - 多种格式匹配
    search_patterns = [
        r'^搜索[：:]\s*(.+)',
        r'^搜索[网页联网]*[：:]\s*(.+)',
        r'^搜索(.{2,})',
        r'^查一下(.+)',
        r'^帮我搜[索]*[：:]*\s*(.+)',
        r'^搜(.{2,})',
    ]
    for p in search_patterns:
        m = re.match(p, s)
        if m:
            query = m.group(1).strip()
            if len(query) >= 2:
                return "web_search", query

    # 代码执行
    m = re.match(r'^运行代码[：:]\s*(.+)', s, re.DOTALL)
    if m:
        return "run_code", m.group(1)
    m = re.match(r'^执行代码[：:]\s*(.+)', s, re.DOTALL)
    if m:
        return "run_code", m.group(1)

    # 执行上一条代码
    if s in ['运行', '执行', '运行代码', '执行代码', '跑一下', 'run']:
        return "run_last_code", ""

    # 搜索记忆
    m = re.match(r'^搜索记忆[：:]\s*(.+)', s, re.I)
    if m:
        return "search_memory", m.group(1)

    # 计算
    m = re.match(r'^计算\s*(.+)$', s)
    if m:
        return "calculator", m.group(1)
    if re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', s) and len(s) > 1:
        return "calculator", s

    # 文本统计
    m = re.match(r'^统计[文本]*[：:]\s*(.+)', s, re.DOTALL)
    if m:
        return "text_stats", m.group(1)

    return None, None

# ==================== AI调用 ====================
def get_client(config):
    return OpenAI(api_key=config["api_key"] or "sk-placeholder", base_url=config["api_base"])

def chat_stream(config, messages):
    client = get_client(config)
    try:
        response = client.chat.completions.create(
            model=config["model_name"], messages=messages,
            temperature=config["temperature"], max_tokens=config["max_tokens"], stream=True,
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"\n\n⚠️ 调用出错：{e}\n\n请检查API地址和密钥。"

# ==================== 初始化 ====================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_content" not in st.session_state:
    st.session_state.uploaded_content = None
if "uploaded_name" not in st.session_state:
    st.session_state.uploaded_name = None

config = load_config()
memory = load_memory()
user_facts = load_user_facts()

# ==================== 侧边栏 ====================
with st.sidebar:
    st.markdown("### 🐼 Panda Agent")
    st.caption("v0.4 · 开源免费")

    conv_count = len(get_conversation_list())
    fact_count = len(user_facts.get("facts", []))
    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card"><div class="num">{memory['total_messages']}</div><div class="label">消息</div></div>
        <div class="stat-card"><div class="num">{conv_count}</div><div class="label">对话</div></div>
        <div class="stat-card"><div class="num">{fact_count}</div><div class="label">记忆</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    if st.button("🆕 新对话", use_container_width=True, type="primary"):
        if st.session_state.messages:
            save_conversation(st.session_state.messages)
            memory["total_messages"] += len(st.session_state.messages)
            save_memory(memory)
        st.session_state.messages = []
        st.session_state.uploaded_content = None
        st.session_state.uploaded_name = None
        st.rerun()
    st.divider()

    with st.expander("💬 历史对话"):
        convs = get_conversation_list()
        if convs:
            for c in convs[:10]:
                label = f"{c['time'][:10]} · {c['preview']}"
                if st.button(label, key=c["file"], use_container_width=True):
                    st.session_state.messages = load_conversation(c["file"])
                    st.rerun()
        else:
            st.caption("暂无")

    with st.expander("📁 文件分析"):
        uploaded = st.file_uploader("上传文件", type=['txt','md','py','json','csv','pdf','html','xml','yaml','yml','log','ini','js','css'])
        if uploaded:
            st.caption(f"📄 {uploaded.name} ({len(uploaded.getvalue())} 字节)")
            if st.button("📖 加载文件", use_container_width=True):
                content = extract_file_content(uploaded)
                st.session_state.uploaded_content = content
                st.session_state.uploaded_name = uploaded.name
                st.session_state.messages.append({
                    "role": "user",
                    "content": f"[已上传文件：{uploaded.name}]\n\n文件内容：\n```\n{content[:3000]}\n```"
                })
                st.rerun()

    with st.expander("🔧 工具箱"):
        st.markdown("""
        <div class="tool-hint">
        <code>搜索：关键词</code> → 联网搜索<br>
        <code>运行代码：print("hi")</code> → 执行代码<br>
        <code>运行</code> → 执行AI写的代码<br>
        <code>计算 3.14*10</code> → 数学计算<br>
        <code>统计：文本</code> → 文本统计<br>
        <code>搜索记忆：关键词</code> → 搜索历史
        </div>
        """, unsafe_allow_html=True)

    with st.expander("🧠 记忆管理"):
        if user_facts.get("facts"):
            for f in user_facts["facts"][-8:]:
                st.markdown(f'<div class="memory-item">{f}</div>', unsafe_allow_html=True)
        else:
            st.caption("多聊聊，Panda会记住你。")
        if st.button("📥 导出全部数据", use_container_width=True):
            export = {"config": {k:v for k,v in config.items() if k!="api_key"}, "memory": memory, "user_facts": user_facts}
            st.download_button("⬇️ 下载", json.dumps(export, ensure_ascii=False, indent=2),
                               file_name=f"panda_{datetime.now().strftime('%Y%m%d')}.json", mime="application/json")

    st.divider()

    with st.expander("⚙️ 模型设置", expanded=not config["api_key"]):
        api_base = st.text_input("API 地址", value=config["api_base"])
        api_key = st.text_input("API 密钥", value=config["api_key"], type="password")
        model_name = st.text_input("模型名称", value=config["model_name"])
        temperature = st.slider("创造性", 0.0, 1.5, config["temperature"], 0.1)
        max_tokens = st.slider("最大回复", 256, 4096, config["max_tokens"], 256)
        if st.button("💾 保存设置", use_container_width=True):
            config.update({"api_base": api_base, "api_key": api_key, "model_name": model_name,
                          "temperature": temperature, "max_tokens": max_tokens})
            save_config(config)
            st.success("已保存")

    with st.expander("🎭 人格设置"):
        agent_name = st.text_input("名称", value=config["agent_name"])
        system_prompt = st.text_area("提示词", value=config["system_prompt"], height=220)
        if st.button("💾 保存人格", use_container_width=True):
            config["agent_name"] = agent_name
            config["system_prompt"] = system_prompt
            save_config(config)
            st.success("已保存")

    st.divider()
    st.caption("🐼 数据100%本地化")

# ==================== 主界面 ====================
st.markdown(f"""
<div class="panda-banner">
    {AVATAR_IMG_TAG}
    <div class="text-area">
        <h1>PANDA AGENT</h1>
        <p class="subtitle">三层记忆 · 代码执行 · 联网搜索 · 文件分析 · 人格自定义</p>
        <span class="version">v0.4</span>
    </div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.messages:
    with st.chat_message("assistant", avatar=AVATAR_DATA_URI):
        st.markdown(f"""**你好，我是 {config['agent_name']}。**

我现在能做的事：
- 🔍 **联网搜索** — `搜索：今天的科技新闻`
- ⚙️ **执行代码** — `运行代码：print("hello")` 或 `运行`
- 📁 **分析文件** — 在左侧上传文件，然后问我问题
- 🧠 **记住你** — 你告诉我的事情我会记住
- 🛡️ **保护你** — 遇到可疑方案会提醒你

试试跟我聊聊。""")

for msg in st.session_state.messages:
    avatar = AVATAR_DATA_URI if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ==================== 输入处理 ====================
if prompt := st.chat_input("跟Panda聊聊..."):
    if not config.get("api_key"):
        st.error("⚠️ 请先在左侧「模型设置」填写API密钥")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    tool_type, tool_input = detect_tool_call(prompt)

    # ===== 联网搜索 =====
    if tool_type == "web_search":
        search_output, raw = tool_web_search(tool_input)
        with st.chat_message("assistant", avatar=AVATAR_DATA_URI):
            st.markdown(search_output)
        st.session_state.messages.append({"role": "assistant", "content": search_output})

        # AI基于搜索结果分析
        ai_msg = [
            {"role": "system", "content": config["system_prompt"]},
            {"role": "system", "content": "以下是用户搜索「" + tool_input + "」获得的实时新闻结果，请基于这些内容为用户做简要分析和总结。不要说你无法联网，因为你已经拿到了搜索结果。"},
            {"role": "user", "content": search_output}
        ]
        with st.chat_message("assistant", avatar=AVATAR_DATA_URI):
            analysis = st.write_stream(chat_stream(config, ai_msg))
        st.session_state.messages.append({"role": "assistant", "content": analysis})

    # ===== 代码执行 =====
    elif tool_type == "run_code":
        output = tool_run_code(tool_input)
        display = f"⚙️ **执行代码：**\n\n```python\n{tool_input}\n```\n\n**输出：**\n```\n{output}\n```"
        with st.chat_message("assistant", avatar=AVATAR_DATA_URI):
            st.markdown(display)
        st.session_state.messages.append({"role": "assistant", "content": display})

    elif tool_type == "run_last_code":
        code = extract_last_code_block(st.session_state.messages)
        if code:
            output = tool_run_code(code)
            display = f"⚙️ **执行代码：**\n\n```python\n{code}\n```\n\n**输出：**\n```\n{output}\n```"
        else:
            display = "⚠️ 没有找到可执行的代码块。让Panda先写一段代码吧。"
        with st.chat_message("assistant", avatar=AVATAR_DATA_URI):
            st.markdown(display)
        st.session_state.messages.append({"role": "assistant", "content": display})

    # ===== 计算器 =====
    elif tool_type == "calculator":
        result = tool_calculator(tool_input)
        display = f"🔧 **计算：**\n\n```\n{result}\n```"
        with st.chat_message("assistant", avatar=AVATAR_DATA_URI):
            st.markdown(display)
        st.session_state.messages.append({"role": "assistant", "content": display})

    # ===== 文本统计 =====
    elif tool_type == "text_stats":
        result = tool_text_stats(tool_input)
        display = f"🔧 **统计：**\n\n```\n{result}\n```"
        with st.chat_message("assistant", avatar=AVATAR_DATA_URI):
            st.markdown(display)
        st.session_state.messages.append({"role": "assistant", "content": display})

    # ===== 搜索记忆 =====
    elif tool_type == "search_memory":
        results = search_conversations(tool_input)
        if results:
            text = f"🔍 **搜索「{tool_input}」：**\n\n"
            for i, r in enumerate(results, 1):
                text += f"**{i}. [{r['role']}]** {r['content']}\n\n"
        else:
            text = f"🔍 没有找到「{tool_input}」相关记忆。"
        with st.chat_message("assistant", avatar=AVATAR_DATA_URI):
            st.markdown(text)
        st.session_state.messages.append({"role": "assistant", "content": text})

    # ===== 正常AI对话 =====
    else:
        full = [{"role": "system", "content": config["system_prompt"]}]

        if user_facts.get("facts"):
            full.append({"role": "system", "content": "关于用户：\n" + "\n".join(f"- {f}" for f in user_facts["facts"][-15:])})

        if st.session_state.uploaded_content:
            full.append({"role": "system", "content": f"用户上传了文件「{st.session_state.uploaded_name}」，内容：\n{st.session_state.uploaded_content[:5000]}"})

        relevant = search_conversations(prompt, max_results=3)
        if relevant:
            mem = "相关历史：\n" + "\n".join(f"[{r['role']}] {r['content']}" for r in relevant)
            full.append({"role": "system", "content": mem})

        full.extend(st.session_state.messages[-20:])

        with st.chat_message("assistant", avatar=AVATAR_DATA_URI):
            response = st.write_stream(chat_stream(config, full))
        st.session_state.messages.append({"role": "assistant", "content": response})

        if len(st.session_state.messages) % 6 == 0:
            try:
                ext = [{"role": "system", "content": "提取用户个人信息（名字、职业、兴趣等），每条一行加- 。没有则输出「无」。"},
                       *st.session_state.messages[-6:]]
                resp = get_client(config).chat.completions.create(model=config["model_name"], messages=ext, temperature=0.3, max_tokens=200)
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
