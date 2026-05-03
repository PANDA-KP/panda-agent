"""
🐼 Panda Agent v0.81
百度搜索优化 | 链接可跳转 | 回复风格修复 | 图片分析 | 自动摘要 | 语义记忆 | 智能工具 | 自动路由
"""

import streamlit as st
import json
import os
import re
import yaml
import base64
import subprocess
import tempfile
import requests
from datetime import datetime
from pathlib import Path
from openai import OpenAI

try:
    from baidusearch.baidusearch import search as baidu_search
    HAS_BAIDU = True
except ImportError:
    HAS_BAIDU = False

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

st.set_page_config(page_title="Panda Agent", page_icon="🐼", layout="wide", initial_sidebar_state="expanded")

AVATAR_PATH = Path(__file__).parent / "panda_avatar.png"
if AVATAR_PATH.exists():
    with open(AVATAR_PATH, "rb") as f:
        AVATAR_B64 = base64.b64encode(f.read()).decode()
else:
    AVATAR_B64 = None

st.markdown("""
<style>
    .stApp { background: #FAFAF8; }
    section[data-testid="stSidebar"] { background: #F7F6F3; }
    footer { display: none; }
    header { display: none; }
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path("panda_data")
CONVERSATIONS_DIR = DATA_DIR / "conversations"
MEMORY_FILE = DATA_DIR / "memory.json"
CONFIG_FILE = DATA_DIR / "config.yaml"
FACTS_FILE = DATA_DIR / "user_facts.json"

for d in [DATA_DIR, CONVERSATIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

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
    "enable_function_calling": False,
}

PERSONA_PRESETS = {
    "Panda（默认）": {"agent_name": "Panda", "agent_avatar": "🐼", "agent_persona": "务实、直接、温暖", "agent_voice": "直接、不绕弯子，重要信息加粗，复杂内容用列表整理", "agent_rules": "永远不索要财务信息\n永远不假装有情感需求\n用户隐私数据绝不外传\n遇到可疑方案主动预警"},
    "小智（热情开朗）": {"agent_name": "小智", "agent_avatar": "😊", "agent_persona": "热情开朗、积极向上", "agent_voice": "语气活泼热情，经常鼓励用户", "agent_rules": "永远保持积极乐观\n用轻松的方式回答\n遇到困难先鼓励再给方案"},
    "老张（沉稳老练）": {"agent_name": "老张", "agent_avatar": "👨‍💼", "agent_persona": "沉稳老练、经验丰富", "agent_voice": "言简意赅，偶尔讲讲人生道理", "agent_rules": "少废话，多给干货\n不浮夸，实事求是"},
    "小美（温柔细腻）": {"agent_name": "小美", "agent_avatar": "🌸", "agent_persona": "温柔细腻、善解人意", "agent_voice": "语气温柔，善于倾听，先共情再给建议", "agent_rules": "先理解用户感受再回答\n不评判用户的选择"},
    "教授（学术严谨）": {"agent_name": "教授", "agent_avatar": "👨‍🏫", "agent_persona": "学术严谨、逻辑清晰", "agent_voice": "用词精确，逻辑严密，分点论述", "agent_rules": "回答要有依据\n鼓励独立思考"},
    "码农（技术范）": {"agent_name": "码农", "agent_avatar": "💻", "agent_persona": "技术宅、效率至上", "agent_voice": "说话简洁高效，能用代码解决就用代码", "agent_rules": "效率第一\n给出可执行方案"},
}

MODEL_REGISTRY = {
    "通用对话": {"models": [{"id": "mimo-v2.5-pro", "name": "MiMo V2.5 Pro", "desc": "旗舰，最强"}, {"id": "mimo-v2.5", "name": "MiMo V2.5", "desc": "均衡性价比"}, {"id": "mimo-v2-pro", "name": "MiMo V2 Pro", "desc": "稳定可靠"}, {"id": "mimo-v2-flash", "name": "MiMo V2 Flash", "desc": "快速便宜"}], "api_base": "https://api.xiaomimimo.com/v1"},
    "多模态": {"models": [{"id": "mimo-v2-omni", "name": "MiMo V2 Omni", "desc": "图片+文字"}], "api_base": "https://api.xiaomimimo.com/v1"},
    "语音合成": {"models": [{"id": "mimo-v2.5-tts", "name": "V2.5 TTS", "desc": "语音合成"}, {"id": "mimo-v2.5-tts-voicedesign", "name": "TTS 声音设计", "desc": "自定义风格"}, {"id": "mimo-v2.5-tts-voiceclone", "name": "TTS 声音克隆", "desc": "克隆声音"}, {"id": "mimo-v2-tts", "name": "V2 TTS", "desc": "基础语音"}], "api_base": "https://api.xiaomimimo.com/v1"},
}


def get_model_list():
    models = []
    for cat, info in MODEL_REGISTRY.items():
        for m in info["models"]:
            models.append({**m, "category": cat, "api_base": info["api_base"]})
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
    for i, m in enumerate(get_model_list()):
        if m["id"] == current_id:
            return get_model_display_list()[i]
    return get_model_display_list()[0]


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
    """构建强化版系统提示词，确保人格和风格生效"""
    name = config.get("agent_name", "Panda")
    persona = config.get("agent_persona", "")
    voice = config.get("agent_voice", "")
    rules = config.get("agent_rules", "")

    parts = []
    parts.append(f"你是{name}。你必须始终以{name}的身份回答。")
    if persona:
        parts.append(f"你的性格：{persona}")
    if voice:
        parts.append(f"你的说话方式：{voice}")
    if rules:
        parts.append(f"你必须遵守的规则：\n{rules}")

    parts.append("""
你的核心行为准则：
1. 直接回答问题，不要说"亲爱的朋友"、"我能感受到"这类客套话
2. 不要猜测用户的动机或身份，只回答被问到的内容
3. 搜索结果用简洁的列表呈现，不要长篇大论分析
4. 如果搜索结果不相关，直接说"没搜到相关结果"，不要硬凑分析
5. 回答控制在3-5句话以内，除非用户要求详细说明
6. 不要用"别担心"、"别着急"这类居高临下的语气
""")

    return "\n\n".join(parts)


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


def semantic_memory_search(query, facts, max_results=5):
    if not facts:
        return []
    query_words = set(re.findall(r'[\w\u4e00-\u9fff]+', query.lower()))
    if not query_words:
        return facts[-max_results:]
    scored = []
    for fact in facts:
        fact_words = set(re.findall(r'[\w\u4e00-\u9fff]+', fact.lower()))
        overlap = len(query_words & fact_words)
        scored.append((overlap, fact))
    scored.sort(key=lambda x: x[0], reverse=True)
    matched = [f for score, f in scored if score > 0]
    if matched:
        return matched[:max_results]
    return facts[-max_results:]


def save_conversation(messages):
    if len(messages) <= 1:
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(CONVERSATIONS_DIR / f"conv_{ts}.json", "w", encoding="utf-8") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "messages": messages}, f, ensure_ascii=False, indent=2)


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


# ==================== 搜索（百度 + RSS，过滤废数据，链接可跳转） ====================
BAIDU_GARBAGE_PATTERNS = [
    r'大家还在搜',
    r'相关搜索',
    r'百度百科',
    r'百度知道',
    r'百度贴吧',
    r'百度文库',
    r'百度经验',
    r'百度首页',
    r'百度一下',
    r'百度搜索',
    r'/s\?',
    r'wd=%',
    r'usm=',
    r'rsv_',
    r'官方网站',
    r'官网直营',
    r'官方商城',
    r'小米网 -',
    r'Xiaomi官方网站',
]


def is_garbage_result(item):
    title = item.get("title", "")
    url = item.get("link", "")
    for pattern in BAIDU_GARBAGE_PATTERNS:
        if re.search(pattern, title, re.I) or re.search(pattern, url, re.I):
            return True
    if len(title.strip()) < 5:
        return True
    if not url or url.strip() == "":
        return True
    return False


def clean_summary(text):
    if not text:
        return ""
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'^\d{4}年\d{1,2}月\d{1,2}日', '', text).strip()
    return text[:200]


def resolve_baidu_url(url):
    """解析百度跟踪链接为真实URL"""
    if 'baidu.com/link' not in url:
        return url
    try:
        resp = requests.head(url, allow_redirects=True, timeout=5)
        return resp.url
    except:
        return url


def tool_web_search(query, max_results=5):
    results = []

    # 引擎1：百度搜索
    if HAS_BAIDU:
        try:
            baidu_results = baidu_search(query, num_results=max_results + 5)
            for r in baidu_results:
                item = {
                    "source": "百度",
                    "title": r.get("title", "").strip(),
                    "summary": clean_summary(r.get("abstract", "")),
                    "link": r.get("url", "").strip()
                }
                if not is_garbage_result(item):
                    results.append(item)
        except:
            pass

    # 引擎2：RSS新闻源
    if HAS_FEED:
        rss_sources = [
            ("新华网", "http://www.news.cn/rss/politics.xml"),
            ("新华网财经", "http://www.news.cn/rss/fortune.xml"),
            ("新华网科技", "http://www.news.cn/rss/tech.xml"),
            ("36氪", "https://36kr.com/feed"),
            ("IT之家", "https://www.ithome.com/rss/"),
            ("少数派", "https://sspai.com/feed"),
        ]
        query_words = [w for w in re.split(r'[\s，。、]+', query.lower()) if len(w) >= 1]
        rss_items = []
        for name, url in rss_sources:
            try:
                feed = feedparser.parse(url)
                for e in feed.entries[:20]:
                    title = getattr(e, 'title', '')
                    summary = re.sub(r'<[^>]+>', '', getattr(e, 'summary', title))[:300]
                    link = getattr(e, 'link', '')
                    score = sum(3 if w in title.lower() else 0 + 1 if w in summary.lower() else 0 for w in query_words)
                    rss_items.append({"source": name, "title": title, "summary": summary, "link": link, "score": score})
            except:
                continue
        matched = sorted([s for s in rss_items if s["score"] > 0], key=lambda x: x["score"], reverse=True)
        if matched:
            results.extend(matched[:max_results])
        elif not results:
            results.extend(rss_items[:max_results])

    if not results:
        return "⚠️ 搜索失败，请检查网络连接", []

    # 去重
    seen = set()
    unique = []
    for r in results:
        key = r["title"][:30]
        if key not in seen:
            seen.add(key)
            unique.append(r)
    results = unique[:max_results]

    # 输出，链接嵌套在标题里
    output = f"🔍 搜索「{query}」：\n\n"
    for i, r in enumerate(results, 1):
        link = resolve_baidu_url(r.get('link', ''))
        title = r['title']

        if link:
            output += f"**{i}. [{title}]({link})**\n"
        else:
            output += f"**{i}. {title}**\n"

        if r.get('summary') and r['summary'] != r['title']:
            output += f"{r['summary']}\n"
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
    for d in ['os.system', 'subprocess.call', 'subprocess.run', 'shutil.rmtree', 'os.remove', '__import__']:
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
    if ext in ['txt','md','py','json','csv','html','xml','yaml','yml','log','ini','js','css','java','c','cpp']:
        return uploaded_file.read().decode('utf-8', errors='ignore')[:50000]
    elif ext == 'pdf':
        if not HAS_PDF:
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
    if m: return "run_code", m.group(1)
    m = re.match(r'^执行代码[：:]\s*(.+)', s, re.DOTALL)
    if m: return "run_code", m.group(1)
    if s in ['运行', '执行', 'run']: return "run_last_code", ""
    m = re.match(r'^搜索记忆[：:]\s*(.+)', s, re.I)
    if m: return "search_memory", m.group(1)
    m = re.match(r'^计算\s*(.+)$', s)
    if m: return "calculator", m.group(1)
    if re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', s) and len(s) > 1: return "calculator", s
    m = re.match(r'^统计[：:]\s*(.+)', s, re.DOTALL)
    if m: return "text_stats", m.group(1)
    return None, None


# ==================== 自动摘要 ====================
def auto_summarize(config, messages):
    if len(messages) <= 30:
        return messages
    old_messages = messages[:20]
    recent_messages = messages[20:]
    old_text = ""
    for msg in old_messages:
        role = "用户" if msg["role"] == "user" else "助手"
        content = msg["content"] if isinstance(msg["content"], str) else str(msg["content"])
        old_text += f"{role}: {content[:200]}\n"
    summary_prompt = [
        {"role": "system", "content": "将以下对话压缩成简洁摘要。保留：用户身份信息、重要结论、未完成的任务、关键偏好。用中文，200字以内。"},
        {"role": "user", "content": old_text[:4000]}
    ]
    try:
        client = OpenAI(api_key=config.get("api_key", "sk"), base_url=config.get("api_base"))
        resp = client.chat.completions.create(model="mimo-v2-flash", messages=summary_prompt, temperature=0.3, max_tokens=300)
        summary = resp.choices[0].message.content
        return [{"role": "system", "content": f"[之前的对话摘要] {summary}"}] + recent_messages
    except:
        return messages[-20:]


# ==================== Function Calling ====================
TOOL_DEFINITIONS = [
    {"type": "function", "function": {"name": "web_search", "description": "搜索互联网获取最新新闻和信息", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "搜索关键词"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "run_python_code", "description": "执行Python代码", "parameters": {"type": "object", "properties": {"code": {"type": "string", "description": "Python代码"}}, "required": ["code"]}}},
    {"type": "function", "function": {"name": "calculate", "description": "计算数学表达式", "parameters": {"type": "object", "properties": {"expression": {"type": "string", "description": "数学表达式"}}, "required": ["expression"]}}}
]


def execute_tool_call(tool_name, arguments):
    if tool_name == "web_search":
        result, _ = tool_web_search(arguments.get("query", ""))
        return result
    elif tool_name == "run_python_code":
        return tool_run_code(arguments.get("code", ""))
    elif tool_name == "calculate":
        return tool_calculator(arguments.get("expression", ""))
    else:
        return f"未知工具：{tool_name}"


# ==================== AI引擎 ====================
def get_model_fallback_chain(config):
    current_id = config.get("model_name", "mimo-v2-flash")
    current_cat = next((m["category"] for m in get_model_list() if m["id"] == current_id), None)
    if not current_cat:
        return [{"id": current_id, "api_base": config.get("api_base")}]
    return [{"id": m["id"], "api_base": m["api_base"]} for m in get_model_list() if m["category"] == current_cat]


def get_model_key_pairs(config):
    api_keys_dict = config.get("api_keys", {})
    auto_routing = config.get("auto_routing", True)
    primary_id = config.get("model_name", "mimo-v2-flash")
    primary_base = config.get("api_base", "https://api.xiaomimimo.com/v1")
    primary_keys = api_keys_dict.get(primary_id, [])
    if not primary_keys and config.get("api_key"):
        primary_keys = [config["api_key"]]
    if not primary_keys:
        primary_keys = ["sk-placeholder"]
    yield {"id": primary_id, "api_base": primary_base}, primary_keys
    if auto_routing:
        for mi in get_model_fallback_chain(config):
            if mi["id"] != primary_id:
                keys = api_keys_dict.get(mi["id"], [])
                if keys:
                    yield mi, keys


def chat_stream(config, messages):
    use_fc = config.get("enable_function_calling", False)
    for model_info, keys in get_model_key_pairs(config):
        model_id = model_info["id"]
        api_base = model_info["api_base"]
        for key_idx, key in enumerate(keys):
            try:
                client = OpenAI(api_key=key or "sk-placeholder", base_url=api_base)
                if use_fc:
                    try:
                        response = client.chat.completions.create(model=model_id, messages=messages, tools=TOOL_DEFINITIONS, tool_choice="auto", temperature=config["temperature"], max_tokens=config["max_tokens"])
                        msg = response.choices[0].message
                        if msg.tool_calls:
                            tool_msgs = [{"role": "assistant", "content": msg.content or "", "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg.tool_calls]}]
                            for tc in msg.tool_calls:
                                args = json.loads(tc.function.arguments)
                                result = execute_tool_call(tc.function.name, args)
                                tool_msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result[:2000]})
                            all_msgs = messages + tool_msgs
                            stream = client.chat.completions.create(model=model_id, messages=all_msgs, temperature=config["temperature"], max_tokens=config["max_tokens"], stream=True)
                            for chunk in stream:
                                if chunk.choices and chunk.choices[0].delta.content:
                                    yield chunk.choices[0].delta.content
                            if model_id != config.get("model_name"):
                                yield f"\n\n---\n*🔄 已切换到 {model_id}*"
                            return
                        else:
                            yield msg.content
                            return
                    except Exception:
                        pass
                response = client.chat.completions.create(model=model_id, messages=messages, temperature=config["temperature"], max_tokens=config["max_tokens"], stream=True)
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                if model_id != config.get("model_name"):
                    yield f"\n\n---\n*🔄 已切换到 {model_id}*"
                return
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "auth" in error_msg.lower() or "403" in error_msg: continue
                if "timeout" in error_msg.lower() or "connect" in error_msg.lower() or "502" in error_msg or "503" in error_msg: break
                continue
    yield "\n\n⚠️ **连接失败**\n\n请检查：\n- API密钥是否有效\n- 网络是否正常\n- 账户是否有余额\n\n👉 点击左侧 ⚙️ 设置"


# ==================== Session ====================
for key, default in [
    ("messages", []), ("uploaded_content", None), ("uploaded_name", None),
    ("uploaded_image", None), ("uploaded_image_name", None),
    ("right_outputs", {"search": "", "code": "", "tool": ""}),
    ("confirm_delete", None), ("page", "chat"), ("show_right_panel", False)
]:
    if key not in st.session_state:
        st.session_state[key] = default

config = load_config()
memory = load_memory()
user_facts = load_user_facts()

# ==================== 新手引导 ====================
if not config.get("api_key") and not config.get("setup_done"):
    st.markdown("## 🐼 欢迎使用 Panda Agent")
    st.markdown("### 只需要一步就能开始")
    st.markdown("1. 点击下方按钮，打开小米MiMo开放平台\n2. 用手机号注册并登录\n3. 点击左侧「API Keys」→「新建API Key」\n4. 复制密钥，粘贴到下方")
    st.link_button("🔗 打开小米MiMo开放平台（免费注册）", "https://platform.xiaomimimo.com", use_container_width=True)
    api_key_input = st.text_input("📋 粘贴你的API密钥", placeholder="sk-xxxxxxxxxxxxxxxx", type="password")
    if st.button("✅ 开始使用", use_container_width=True, type="primary"):
        if api_key_input and api_key_input.strip():
            config["api_key"] = api_key_input.strip()
            config["api_keys"] = {"mimo-v2-flash": [api_key_input.strip()]}
            config["setup_done"] = True
            save_config(config)
            st.success("设置成功！")
            import time; time.sleep(1); st.rerun()
        else:
            st.warning("请先粘贴API密钥")
    with st.expander("💡 常见问题"):
        st.markdown("**要花钱吗？** 新用户有免费额度。\n\n**密钥安全吗？** 只存在你电脑上。\n\n**想先看看界面？** 点下方跳过。")
        if st.button("⏭️ 先看看界面"):
            config["setup_done"] = True
            save_config(config); st.rerun()
    st.stop()

# ==================== 左侧栏 ====================
with st.sidebar:
    avatar_display = config.get("agent_avatar", "🐼")
    st.markdown(f"### {avatar_display} Panda Agent")
    st.caption("v0.81")
    if st.button("🆕 新对话", use_container_width=True, type="primary"):
        if st.session_state.messages:
            save_conversation(st.session_state.messages)
            memory["total_messages"] += len(st.session_state.messages)
            save_memory(memory)
        st.session_state.messages = []
        st.session_state.right_outputs = {"search": "", "code": "", "tool": ""}
        st.session_state.uploaded_content = None
        st.session_state.uploaded_image = None
        st.session_state.uploaded_image_name = None
        st.session_state.confirm_delete = None
        st.rerun()
    st.markdown("")
    st.markdown("**💬 历史对话**")
    convs = get_conversation_list()
    if convs:
        for c in convs[:10]:
            col_btn, col_del = st.columns([5, 1])
            with col_btn:
                if st.button(f"{c['time'][:10]} {c['preview']}", key=f"l_{c['file']}", use_container_width=True):
                    st.session_state.messages = load_conversation(c["file"]); st.rerun()
            with col_del:
                if st.button("🗑️", key=f"d_{c['file']}", help="删除"):
                    st.session_state.confirm_delete = c['file']; st.rerun()
        if st.session_state.confirm_delete:
            st.warning("确认删除？")
            y, n = st.columns(2)
            with y:
                if st.button("✅ 确认", use_container_width=True):
                    delete_conversation(st.session_state.confirm_delete)
                    st.session_state.confirm_delete = None; st.rerun()
            with n:
                if st.button("❌ 取消", use_container_width=True):
                    st.session_state.confirm_delete = None; st.rerun()
    else:
        st.caption("暂无")
    st.divider()

    st.markdown("**📁 上传文件**")
    st.caption("支持文档和图片")
    uploaded = st.file_uploader("选择文件", type=['txt','md','py','json','csv','pdf','html','xml','yaml','yml','log','ini','js','css','png','jpg','jpeg','gif','webp'], label_visibility="collapsed")
    if uploaded:
        ext = uploaded.name.split('.')[-1].lower()
        is_image = ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']
        if is_image:
            st.image(uploaded, caption=uploaded.name, use_container_width=True)
            if st.button("🔍 分析这张图片", use_container_width=True):
                image_bytes = uploaded.read()
                img_b64 = base64.b64encode(image_bytes).decode()
                mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
                st.session_state.uploaded_image = img_b64
                st.session_state.uploaded_image_name = uploaded.name
                st.session_state.messages.append({"role": "user", "content": f"[上传图片：{uploaded.name}]"})
                st.rerun()
        else:
            st.caption(f"📄 {uploaded.name}")
            if st.button("📖 加载并分析", use_container_width=True):
                content = extract_file_content(uploaded)
                st.session_state.uploaded_content = content
                st.session_state.uploaded_name = uploaded.name
                st.session_state.messages.append({"role": "user", "content": f"[已上传：{uploaded.name}]\n\n```\n{content[:3000]}\n```"})
                st.rerun()
    st.divider()

    col_c, col_s = st.columns(2)
    with col_c:
        if st.button("💬 聊天", use_container_width=True):
            st.session_state.page = "chat"; st.rerun()
    with col_s:
        if st.button("⚙️ 设置", use_container_width=True):
            st.session_state.page = "settings"; st.rerun()
    st.divider()
    st.caption("🐼 数据100%本地化")

# ==================== 设置页面 ====================
if st.session_state.page == "settings":
    st.markdown("## ⚙️ 设置")
    st.markdown("---")
    st.markdown("### 基础设置")
    api_key = st.text_input("API 密钥", value=config.get("api_key", ""), type="password", help="在 platform.xiaomimimo.com 获取")
    persona_names = list(PERSONA_PRESETS.keys())
    current_persona_name = next((pname for pname, pdata in PERSONA_PRESETS.items() if pdata["agent_name"] == config.get("agent_name", "Panda")), persona_names[0])
    selected_persona = st.selectbox("人格", persona_names, index=persona_names.index(current_persona_name))
    if selected_persona in PERSONA_PRESETS:
        p = PERSONA_PRESETS[selected_persona]
        st.caption(f"性格：{p['agent_persona']} | 说话方式：{p['agent_voice'][:40]}")
    with st.expander("▶ 高级设置"):
        st.markdown("**模型选择**")
        model_displays = get_model_display_list()
        current_display = get_current_display(config)
        selected_display = st.selectbox("模型", model_displays, index=model_displays.index(current_display) if current_display in model_displays else 0)
        selected_model = find_model_by_display(selected_display)
        if selected_model:
            st.caption(f"📍 {selected_model['category']} | {selected_model['id']}")
        st.markdown("**多密钥管理**")
        api_keys_dict = config.get("api_keys", {})
        model_id = selected_model["id"] if selected_model else "mimo-v2-flash"
        current_keys = api_keys_dict.get(model_id, [])
        if current_keys:
            for ki, key in enumerate(current_keys):
                masked = key[:8] + "****" + key[-4:] if len(key) > 16 else key[:4] + "****"
                kc, kd = st.columns([4, 1])
                with kc: st.caption(f"🔑 {ki+1}. {masked}")
                with kd:
                    if st.button("🗑️", key=f"rk_{model_id}_{ki}"):
                        current_keys.pop(ki)
                        api_keys_dict[model_id] = current_keys
                        config["api_keys"] = api_keys_dict
                        config["api_key"] = current_keys[0] if current_keys else ""
                        save_config(config); st.rerun()
        new_key = st.text_input("添加密钥", placeholder="sk-xxxxxxxx", type="password", key=f"nk_{model_id}")
        if st.button("➕ 添加", use_container_width=True):
            if new_key and new_key.strip() and new_key.strip() not in current_keys:
                current_keys.append(new_key.strip())
                api_keys_dict[model_id] = current_keys
                config["api_keys"] = api_keys_dict
                if len(current_keys) == 1: config["api_key"] = current_keys[0]
                save_config(config); st.success("已添加"); st.rerun()
        st.markdown("")
        st.markdown("**功能开关**")
        auto_routing = st.toggle("🔄 自动路由（模型断开时自动切换）", value=config.get("auto_routing", True))
        enable_fc = st.toggle("🤖 智能工具调用（AI自动决定何时搜索/计算）", value=config.get("enable_function_calling", False))
        temperature = st.slider("创造性", 0.0, 1.5, config["temperature"], 0.1)
    if st.button("💾 保存设置", use_container_width=True, type="primary"):
        main_key = api_key.strip() if api_key else (api_keys_dict.get(model_id, [None])[0] or "")
        updates = {"api_key": main_key, "auto_routing": auto_routing, "enable_function_calling": enable_fc, "temperature": temperature}
        if selected_model:
            updates["api_base"] = selected_model["api_base"]; updates["model_name"] = selected_model["id"]
        if selected_persona in PERSONA_PRESETS:
            p = PERSONA_PRESETS[selected_persona]
            updates.update({"agent_name": p["agent_name"], "agent_avatar": p["agent_avatar"], "agent_persona": p["agent_persona"], "agent_voice": p["agent_voice"], "agent_rules": p["agent_rules"]})
        updates["system_prompt"] = build_system_prompt({**config, **updates})
        config.update(updates); save_config(config); st.success("设置已保存")
    st.markdown("---")
    st.markdown("### 数据管理")
    col_export, col_clear = st.columns(2)
    with col_export:
        if st.button("📥 导出所有数据", use_container_width=True):
            export = {"config": {k: v for k, v in config.items() if k != "api_key"}, "memory": memory, "user_facts": user_facts}
            st.download_button("⬇️ 下载备份", json.dumps(export, ensure_ascii=False, indent=2), file_name=f"panda_backup_{datetime.now().strftime('%Y%m%d')}.json", mime="application/json", use_container_width=True)
    with col_clear:
        if st.button("🗑️ 清除所有记忆", use_container_width=True):
            user_facts["facts"] = []; save_user_facts(user_facts); st.success("已清除")
    st.markdown("---")
    with st.expander("❓ 常见问题"):
        st.markdown("**API密钥无效？** 去 platform.xiaomimimo.com 确认。\n\n**网络连接失败？** 检查能否打开 platform.xiaomimimo.com。\n\n**什么是自动路由？** 模型连不上时自动切换同类别的其他模型。\n\n**什么是智能工具调用？** 开启后，AI会自动决定何时搜索、计算。\n\n**数据安全吗？** 全部存在你电脑 panda_data 文件夹里。\n\n**怎么搜索？** 输入 `搜索：关键词`，或开启智能工具调用后直接问。\n\n**怎么分析图片？** 左侧上传图片，点「分析这张图片」，然后输入问题。\n\n**自动摘要是什么？** 聊天超过30条时，自动压缩旧消息防止遗忘。")
    with st.expander("📊 当前状态"):
        total_keys = sum(len(v) for v in config.get("api_keys", {}).values() if v)
        st.markdown(f"| 项目 | 状态 |\n|------|------|\n| 模型 | {config.get('model_name')} |\n| 人格 | {config.get('agent_avatar')} {config.get('agent_name')} |\n| 自动路由 | {'开启' if config.get('auto_routing', True) else '关闭'} |\n| 智能工具 | {'开启' if config.get('enable_function_calling', False) else '关闭'} |\n| 密钥 | {total_keys} 个 |\n| 消息 | {memory.get('total_messages', 0)} 条 |\n| 对话 | {len(get_conversation_list())} 个 |\n| 记忆 | {len(user_facts.get('facts', []))} 条 |\n| 版本 | v0.81 |\n| 搜索引擎 | {'百度+RSS' if HAS_BAIDU else 'RSS'} |")
    if st.button("💬 返回聊天", use_container_width=True):
        st.session_state.page = "chat"; st.rerun()

# ==================== 聊天页面 ====================
elif st.session_state.page == "chat":
    avatar_display = config.get("agent_avatar", "🐼")

    if len(st.session_state.messages) > 30:
        st.session_state.messages = auto_summarize(config, st.session_state.messages)

    if st.session_state.show_right_panel:
        col_chat, col_right = st.columns([3, 1])
        with col_right:
            st.markdown("#### 📋 工具面板")
            if st.button("✕ 收起", use_container_width=True):
                st.session_state.show_right_panel = False; st.rerun()
            with st.expander("🔍 搜索结果", expanded=bool(st.session_state.right_outputs["search"])):
                if st.session_state.right_outputs["search"]: st.code(st.session_state.right_outputs["search"][:2000], language=None)
                else: st.caption("输入 搜索：关键词")
            with st.expander("⚙️ 代码输出", expanded=bool(st.session_state.right_outputs["code"])):
                if st.session_state.right_outputs["code"]: st.code(st.session_state.right_outputs["code"][:2000], language=None)
                else: st.caption("输入 运行代码：...")
            with st.expander("📁 文件内容", expanded=bool(st.session_state.uploaded_content)):
                if st.session_state.uploaded_content:
                    st.caption(f"📄 {st.session_state.uploaded_name}"); st.code(st.session_state.uploaded_content[:1500], language=None)
                else: st.caption("左侧上传文件")
            with st.expander("🔧 工具输出", expanded=bool(st.session_state.right_outputs["tool"])):
                if st.session_state.right_outputs["tool"]: st.code(st.session_state.right_outputs["tool"][:1000], language=None)
                else: st.caption("计算、统计等结果")
    else:
        col_chat, col_toggle = st.columns([10, 1])
        with col_toggle:
            if st.button("📋", help="工具面板"):
                st.session_state.show_right_panel = True; st.rerun()

    with col_chat:
        if not st.session_state.messages:
            if st.session_state.uploaded_image:
                st.markdown(f"### {avatar_display} PANDA AGENT\n\n已加载图片 **{st.session_state.uploaded_image_name}**\n\n请输入你想问的问题，比如：\n- 描述这张图片\n- 这张图片里有什么\n- 用中文详细分析这张图片")
            else:
                st.markdown(f"### {avatar_display} PANDA AGENT\n\n你好，我是 **{avatar_display} {config.get('agent_name', 'Panda')}**。\n\n直接输入任何问题开始聊天，或者点击下方试试：")
                st.markdown("")
                cols = st.columns(3)
                examples = [("🔍 搜索小米最新新闻", "搜索：小米最新新闻"), ("🧮 计算 3.14 * 12 * 12", "计算 3.14 * 12 * 12"), ("💻 写一个贪吃蛇游戏", "帮我用Python写一个贪吃蛇游戏"), ("📝 分析人工智能趋势", "帮我分析人工智能未来5年的发展趋势"), ("📊 统计一段文字", "统计：这是一段测试文字看看有多少字"), ("🧠 搜索记忆", "搜索记忆：小米")]
                for i, (label, text) in enumerate(examples):
                    with cols[i % 3]:
                        if st.button(label, key=f"ex_{i}", use_container_width=True):
                            st.session_state.messages.append({"role": "user", "content": text}); st.rerun()

        for msg in st.session_state.messages:
            if msg["role"] == "assistant":
                with st.chat_message("assistant", avatar=avatar_display): st.markdown(msg["content"])
            elif msg["role"] == "user":
                with st.chat_message("user"): st.markdown(msg["content"])

    input_placeholder = "描述这张图片..." if st.session_state.uploaded_image else "问我任何问题..."
    if prompt := st.chat_input(input_placeholder):
        if not config.get("api_key"):
            st.error("⚠️ 请先设置API密钥 👉 点击左侧 ⚙️ 设置"); st.stop()

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        tool_type, tool_input = detect_tool_call(prompt)

        if st.session_state.uploaded_image and tool_type is None:
            img_b64 = st.session_state.uploaded_image
            img_name = st.session_state.uploaded_image_name
            ext = img_name.split('.')[-1].lower()
            mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
            img_msg = [
                {"role": "system", "content": config.get("system_prompt", build_system_prompt(config))},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}}
                ]}
            ]
            with st.chat_message("assistant", avatar=avatar_display):
                response = st.write_stream(chat_stream(config, img_msg))
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.session_state.uploaded_image = None
            st.session_state.uploaded_image_name = None

        elif tool_type == "web_search":
            search_output, _ = tool_web_search(tool_input)
            st.session_state.right_outputs["search"] = search_output
            with st.chat_message("assistant", avatar=avatar_display): st.markdown(search_output)
            st.session_state.messages.append({"role": "assistant", "content": search_output})
            ai_msg = [
                {"role": "system", "content": config.get("system_prompt", build_system_prompt(config))},
                {"role": "system", "content": f"以下是搜索「{tool_input}」的结果。请用简洁列表呈现，每条1-2句话概括，不要长篇分析。如果结果不相关，直接说没搜到。"},
                {"role": "user", "content": search_output}
            ]
            with st.chat_message("assistant", avatar=avatar_display):
                analysis = st.write_stream(chat_stream(config, ai_msg))
            st.session_state.messages.append({"role": "assistant", "content": analysis})

        elif tool_type == "run_code":
            output = tool_run_code(tool_input)
            st.session_state.right_outputs["code"] = f"代码：\n{tool_input}\n\n输出：\n{output}"
            display = f"```python\n{tool_input}\n```\n\n输出：\n```\n{output}\n```"
            with st.chat_message("assistant", avatar=avatar_display): st.markdown(display)
            st.session_state.messages.append({"role": "assistant", "content": display})

        elif tool_type == "run_last_code":
            code = extract_last_code_block(st.session_state.messages)
            if code:
                output = tool_run_code(code)
                st.session_state.right_outputs["code"] = f"代码：\n{code}\n\n输出：\n{output}"
                display = f"```python\n{code}\n```\n\n输出：\n```\n{output}\n```"
            else:
                display = "⚠️ 没有找到代码块。先让Panda写代码，然后输入「运行」。"
            with st.chat_message("assistant", avatar=avatar_display): st.markdown(display)
            st.session_state.messages.append({"role": "assistant", "content": display})

        elif tool_type == "calculator":
            result = tool_calculator(tool_input)
            st.session_state.right_outputs["tool"] = result
            with st.chat_message("assistant", avatar=avatar_display): st.markdown(f"```\n{result}\n```")
            st.session_state.messages.append({"role": "assistant", "content": result})

        elif tool_type == "text_stats":
            result = tool_text_stats(tool_input)
            st.session_state.right_outputs["tool"] = result
            with st.chat_message("assistant", avatar=avatar_display): st.markdown(f"```\n{result}\n```")
            st.session_state.messages.append({"role": "assistant", "content": result})

        elif tool_type == "search_memory":
            facts = user_facts.get("facts", [])
            relevant = semantic_memory_search(tool_input, facts)
            conv_results = search_conversations(tool_input, max_results=3)
            text = f"🧠 语义搜索「{tool_input}」：\n\n"
            if relevant:
                text += "**记忆匹配：**\n"
                for i, f in enumerate(relevant, 1):
                    text += f"{i}. {f}\n"
            if conv_results:
                text += "\n**对话历史匹配：**\n"
                for i, r in enumerate(conv_results, 1):
                    text += f"{i}. [{r['role']}] {r['content']}\n"
            if not relevant and not conv_results:
                text += "没有找到相关内容"
            with st.chat_message("assistant", avatar=avatar_display): st.markdown(text)
            st.session_state.messages.append({"role": "assistant", "content": text})

        else:
            full = [{"role": "system", "content": config.get("system_prompt", build_system_prompt(config))}]
            facts = user_facts.get("facts", [])
            if facts:
                relevant_facts = semantic_memory_search(prompt, facts, max_results=10)
                full.append({"role": "system", "content": "关于用户：\n" + "\n".join(f"- {f}" for f in relevant_facts)})
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
                    resp = OpenAI(api_key=config.get("api_key", "sk"), base_url=config.get("api_base")).chat.completions.create(model=config["model_name"], messages=ext, temperature=0.3, max_tokens=200)
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
