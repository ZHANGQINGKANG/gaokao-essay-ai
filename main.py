"""
高考满分作文生成系统 —— FastAPI 后端
====================================
功能：
    GET  /          返回网页界面（HTML/CSS/JS 全部内联，无需前端框架）
    POST /generate  接收 {"topic": "作文题目"}，调用智谱 GLM 生成满分作文

运行方式：
    python main.py
    或
    uvicorn main:app --reload

启动后浏览器访问：http://127.0.0.1:8000
"""

import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from openai import OpenAI
from pydantic import BaseModel, Field

from prompt import SYSTEM_PROMPT

# ==========================================================
# ★★★ 在这里修改你的个人信息（会硬编码显示在网页顶部）★★★
# ==========================================================
STUDENT_INFO = "班级：网安241班 | 姓名：张庆康 | 学号：202401050838"

# ---------------- 读取 .env 配置 ----------------
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/").strip()
MODEL_NAME = os.getenv("MODEL_NAME", "glm-4").strip()

# ---------------- 初始化 OpenAI 客户端（兼容智谱 GLM 接口）----------------
client = OpenAI(
    api_key=API_KEY or "not-set",
    base_url=BASE_URL,
    timeout=180.0,   # 生成一篇千字作文通常需要 30~120 秒
    max_retries=2,
)

app = FastAPI(title="高考满分作文生成系统", version="1.0.0")


# ---------------- 请求 / 响应模型 ----------------
class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=4000, description="作文题目或题目材料")


class GenerateResponse(BaseModel):
    essay: str    # 生成的作文全文（首行为标题）
    model: str    # 使用的模型
    elapsed: float  # 生成耗时（秒）


# ---------------- 前端页面（HTML/CSS/JS 内联）----------------
INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>高考满分作文生成系统</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    background: linear-gradient(135deg, #fdf6e3 0%, #f3e3c3 100%);
    min-height: 100vh; color: #3d2c1e;
  }
  .container { max-width: 860px; margin: 0 auto; padding: 34px 20px 70px; }
  header {
    background: linear-gradient(135deg, #8b1a1a, #c0392b);
    color: #fff; border-radius: 16px; padding: 28px 32px;
    box-shadow: 0 6px 18px rgba(139, 26, 26, .25);
  }
  header h1 { font-size: 26px; letter-spacing: 3px; }
  header .sub { margin-top: 8px; font-size: 13px; opacity: .92; }
  .student-info {
    margin-top: 14px; display: inline-block;
    background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.4);
    padding: 7px 16px; border-radius: 999px; font-size: 14px; letter-spacing: 1px;
  }
  .card {
    background: #fff; border-radius: 16px; padding: 26px 30px; margin-top: 20px;
    box-shadow: 0 4px 14px rgba(61, 44, 30, .08);
  }
  label { display: block; font-size: 15px; font-weight: bold; margin-bottom: 10px; }
  textarea {
    width: 100%; min-height: 130px; padding: 14px; font-size: 15px;
    border: 2px solid #e5d5b7; border-radius: 10px; outline: none;
    resize: vertical; line-height: 1.7; font-family: inherit; background: #fffdf7;
  }
  textarea:focus { border-color: #c0392b; }
  .btn-row { display: flex; align-items: center; gap: 14px; margin-top: 16px; }
  button {
    background: linear-gradient(135deg, #c0392b, #8b1a1a); color: #fff;
    border: none; border-radius: 10px; padding: 12px 34px;
    font-size: 16px; cursor: pointer; letter-spacing: 2px;
    transition: opacity .2s, transform .1s;
  }
  button:hover { opacity: .9; }
  button:active { transform: scale(.98); }
  button:disabled { opacity: .55; cursor: not-allowed; }
  .spinner {
    display: none; width: 18px; height: 18px;
    border: 3px solid rgba(255,255,255,.4); border-top-color: #fff;
    border-radius: 50%; animation: spin .8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .tip { font-size: 12px; color: #9c8a75; }
  .error {
    display: none; margin-top: 16px; padding: 12px 16px;
    background: #fdecea; color: #b03a2e; border: 1px solid #f5b7b1;
    border-radius: 10px; font-size: 14px; line-height: 1.6;
  }
  .result { display: none; }
  .result-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
  #essayTitle {
    text-align: center; font-size: 24px; margin: 8px 0 18px;
    font-family: "KaiTi", "楷体", "STKaiti", serif; letter-spacing: 2px;
  }
  #essayBody p {
    font-family: "KaiTi", "楷体", "STKaiti", serif;
    font-size: 17px; line-height: 2.1; text-indent: 2em; margin-bottom: 10px;
  }
  #meta { font-size: 13px; color: #9c8a75; }
  #copyBtn {
    background: #f3e3c3; color: #7a5c2e; padding: 7px 16px;
    font-size: 13px; border-radius: 8px; letter-spacing: 0;
  }
  footer { text-align: center; margin-top: 34px; font-size: 12px; color: #a5937c; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>📝 高考满分作文生成系统</h1>
    <div class="sub">基于生成式人工智能（智谱 GLM 大模型）· 提示词工程实验项目</div>
    <div class="student-info">__STUDENT_INFO__</div>
  </header>

  <div class="card">
    <label for="topic">请输入高考作文题目（也可直接粘贴整段作文材料）：</label>
    <textarea id="topic" placeholder="例如：故事的力量（2023年新课标I卷）&#10;或：本手、妙手、俗手是围棋的三个术语……（2022年新课标I卷）&#10;也可以直接粘贴完整的作文题目材料。"></textarea>
    <div class="btn-row">
      <button id="btn"><span id="btnText">✍️ 生成作文</span></button>
      <div class="spinner" id="loading"></div>
      <span class="tip">生成一篇千字作文约需 30~120 秒，请耐心等待</span>
    </div>
    <div class="error" id="error"></div>
  </div>

  <div class="card result" id="result">
    <div class="result-head">
      <span id="meta"></span>
      <button id="copyBtn">📋 复制全文</button>
    </div>
    <h2 id="essayTitle"></h2>
    <div id="essayBody"></div>
  </div>

  <footer>《生成式人工智能》课程实验 · FastAPI + OpenAI SDK + 智谱 GLM</footer>
</div>

<script>
  const $ = (id) => document.getElementById(id);
  const btn = $('btn'), topicEl = $('topic'), errBox = $('error'), resultBox = $('result');
  let lastEssay = '';

  btn.addEventListener('click', generate);
  topicEl.addEventListener('keydown', (e) => { if (e.ctrlKey && e.key === 'Enter') generate(); });

  function showError(msg) { errBox.textContent = msg; errBox.style.display = 'block'; }
  function hideError() { errBox.style.display = 'none'; }
  function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  async function generate() {
    const topic = topicEl.value.trim();
    hideError();
    if (!topic) { showError('请先输入作文题目或材料'); return; }

    btn.disabled = true;
    $('btnText').textContent = '生成中…';
    $('loading').style.display = 'inline-block';
    resultBox.style.display = 'none';

    try {
      const res = await fetch('/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topic })
      });
      const data = await res.json().catch(() => ({ detail: '服务返回异常' }));
      if (!res.ok) {
        showError(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
        return;
      }
      renderEssay(data.essay, data);
    } catch (err) {
      showError('请求失败：' + err.message + '（若等待时间过长，请重试或检查网络）');
    } finally {
      btn.disabled = false;
      $('btnText').textContent = '✍️ 生成作文';
      $('loading').style.display = 'none';
    }
  }

  function renderEssay(essay, data) {
    const lines = essay.split('\\n').map(s => s.trim()).filter(Boolean);
    let title = '无题';
    if (lines.length > 1) { title = lines.shift(); }
    title = title.replace(/^[#*《》\\s]+|[#*《》\\s]+$/g, '');
    $('essayTitle').textContent = title;
    $('essayBody').innerHTML = lines.map(s => '<p>' + esc(s) + '</p>').join('');
    const charCount = essay.replace(/\\s/g, '').length;
    $('meta').textContent = '全文约 ' + charCount + ' 字 · 耗时 ' +
      (data.elapsed != null ? data.elapsed : '?') + ' 秒 · 模型：' + (data.model || '');
    lastEssay = essay;
    resultBox.style.display = 'block';
    resultBox.scrollIntoView({ behavior: 'smooth' });
  }

  $('copyBtn').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(lastEssay);
      $('copyBtn').textContent = '✅ 已复制';
      setTimeout(() => { $('copyBtn').textContent = '📋 复制全文'; }, 1500);
    } catch (e) {
      $('copyBtn').textContent = '⚠️ 复制失败';
      setTimeout(() => { $('copyBtn').textContent = '📋 复制全文'; }, 1500);
    }
  });
</script>
</body>
</html>"""


# ---------------- 路由 ----------------
@app.get("/", response_class=HTMLResponse)
def index():
    """返回网页界面"""
    return INDEX_HTML.replace("__STUDENT_INFO__", STUDENT_INFO)


@app.post("/generate", response_model=GenerateResponse)
def generate_essay(req: GenerateRequest):
    """接收作文题目，调用智谱 GLM 生成满分作文"""
    # 1. 检查 API Key 是否已配置
    if not API_KEY or "填写" in API_KEY or "your_zhipu" in API_KEY:
        raise HTTPException(
            status_code=400,
            detail="尚未配置 API Key：请打开项目目录下的 .env 文件，将 OPENAI_API_KEY 替换为你的真实智谱 Key，然后重启服务。",
        )

    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="作文题目不能为空。")

    # 2. 调用大模型：SYSTEM_PROMPT 作为 system message，题目作为 user message
    start = time.time()
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"【作文题目】\n{topic}\n\n请根据以上题目，写一篇高考作文。",
                },
            ],
            temperature=0.9,   # 略高的温度以保证文采与创意
            max_tokens=3000,   # 足够容纳 900~1100 字的作文
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"调用大模型失败：{exc}（请检查 API Key 是否有效、账户是否有额度、网络是否畅通）",
        ) from exc

    essay = (completion.choices[0].message.content or "").strip()
    if not essay:
        raise HTTPException(status_code=500, detail="模型未返回内容，请重试，或在 .env 中更换 MODEL_NAME。")

    return GenerateResponse(essay=essay, model=MODEL_NAME, elapsed=round(time.time() - start, 1))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
