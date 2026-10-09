# 抖音登录接口与截图

仓库只保留抖音登录相关代码。搜索页保存、B 站脚本、离线页面处理及其测试和依赖已删除。

`douyin_requests.py` 直接使用 Python `requests` 调用抖音接口，不启动浏览器，也不调用自建 API。`douyin_export.py` 使用 CloakBrowser 和 Playwright 网络拦截，导出网站实际生成的请求（包含签名、请求体和 Cookie）。短信请求在浏览器里会被中止，只由 `requests` 发送。

这不是把任意浏览器代码自动翻译成 HTTP：网站签名、Cookie 和风控可能使捕获的请求无法重放或很快失效。先看真实接口报告，不把测试页面通过当成抖音发送成功。脚本不会破解或代过安全验证。

## 安装

需要 Python 3.10+，远端检查使用 Ubuntu 24.04：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install-deps chromium
```

首次启动 CloakBrowser 会下载浏览器，需要网络。`browser_setup.py` 只导入依赖、检查参数，不自动运行 pip。

## 保存接口二维码

```bash
python douyin_export.py --phone 13657450350
python douyin_requests.py --bundle output/douyin-api/request-bundle.json
```

第一步保存浏览器二维码、截图及二维码请求；第二步通过 `requests` 再调用二维码接口，只接受能解码的真实二维码图片，保存为 `api-login-qr.png`。接口没有返回图片或图片不能解码时会失败，浏览器截图不会冒充接口产物。

## 通过接口发送一次验证码

```bash
# 点击一次以捕获网站生成的短信请求，浏览器的短信请求始终被拦截
python douyin_export.py --phone 13657450350 --capture-sms
# 直接调用抖音接口；先确认接口二维码保存成功，再请求一次短信
python douyin_requests.py --bundle output/douyin-api/request-bundle.json --send-code
```

手机号在导出时确定，重放时不改签名或请求体。`requests` 保留原始 URL、编码后的请求体和必要请求头，不自动重试，不跟随重定向。发送前创建独占的 `.sms-attempted` 文件，同一请求文件即使超时、失败或被两个进程同时使用，也不能再次发送。不要删除这个标记以重试；结果不明确时先检查手机和报告。

导出文件包含会话 Cookie 和签名，文件权限为 `0600`，不要提交或分享。GitHub 手动流程只在当前任务内使用，结束后删除，不上传此文件。签名失效后需重新导出；重新导出不等于获得重复发送授权。

可用 `--output-dir` 选择输出位置，`--timeout-seconds` 设置单次超时。导出时可加 `--headed` 显示窗口；Linux runner 通过 Xvfb 提供桌面。

## 输出与结果

| 文件 | 内容 |
| --- | --- |
| `douyin_dom.js` | 浏览器内使用的 JavaScript 辅助脚本，负责输入框聚焦和精确选择中国区号，不发送短信 |
| `douyin_login.py` | 原有 CloakBrowser 登录入口，仍可独立保存截图 |
| `douyin_export.py` | 捕获实际二维码/短信请求，并拦截浏览器短信发送 |
| `douyin_requests.py` | 不启动浏览器的 Python HTTP 请求入口 |
| `login-qr.png` / `login.png` | 浏览器二维码和页面截图 |
| `before-send.png` / `after-click.png` / `sms-result.png` | 浏览器捕获现场；不证明接口短信成功 |
| `request-bundle.json` | 私密的请求输入，默认在忽略的 `output/` 下 |
| `export-result.json` | 是否捕获接口，以及拦截的浏览器短信请求数量 |
| `api-login-qr.png` | 从 `requests` 接口响应保存且成功解码的二维码 |
| `api-result.json` | 接口 HTTP 状态、业务结果码和发送结果 |
| `api-result.png` | 接口报告生成的结果图片，明确标注不是浏览器截图 |

短信业务结果码明确为 `0`（接受整数或数字字符串），HTTP 为 2xx，且没有失败或安全验证信息时，才记为 `request_accepted`。它表示服务器接受请求，不保证手机已收到。外层 `success` 或 `code: 0` 不会掩盖内层失败；“验证码发送频繁”或 HTTP 429 写为 `failed`，并记录 `reason: rate_limited`。HTTP 200 或消息 `success` 本身不算成功；缺少明确结果写 `unknown`，要求安全验证写 `verification_required`，明确失败写 `failed`。这些情况返回非零退出码。二维码失败、捕获不到短信接口或网络异常也返回失败，不补发短信。报告不包含完整签名 URL、Cookie 或响应令牌。

按钮点击沿用现有逻辑。浏览器从点击前监听整个浏览器上下文的短信请求，等请求完成再读取响应体；网页先显示成功或失败时，会在原有超时范围内等待尚未读完的接口返回，接口失败优先于网页成功提示。`result.json` 中的 `sms_requests` 记录请求过程，`sms_responses` 保存接口状态、结果码和提示，`ui_status` 单独记录网页反馈。`sms_response_state` 区分已收到返回（`completed`）、导出时主动拦截（`blocked`）、网络失败（`network_error`）、响应未完成（`pending_timeout`）和没有观察到请求（`not_observed`）。被浏览器拦截的请求没有服务器返回，不能把拦截当成发送成功。`api-result.json` 和 `api-result.png` 也记录 requests 的返回状态与限流原因。

issue #3 最新说明已确认按钮点击成功，并出现发送频繁提示。本轮保留按钮点击逻辑，优化返回数据处理，通过远端测试接口验证限流、延迟返回、安全验证和非 JSON 返回。实际短信只使用用户明确授权的号码，每个号码最多一次，不把限流当成成功。

## 远端检查

GitHub Actions 的 **Douyin login screenshots** 在 feature 分支 push 和 PR 时运行真实 CloakBrowser 登录测试，以及“浏览器捕获 → 拦截短信 → requests 调用测试接口 → 保存 PNG”的完整检查。测试站点不访问抖音，也不会发真实短信。

手动运行工作流会通过 CloakBrowser 导出抖音请求，再用 `requests` 直接请求抖音。在 `phone` 中填写已获准使用的完整手机号，默认只验证二维码；勾选 `send_code` 才由 `requests` 向该号码尝试一次短信。附件 `douyin-login` 提供 PNG、去掉敏感请求信息的报告及 Python 代码，保留 7 天。

按仓库约定，不进行本地构建、编译或会触发编译的测试。远端检查结果和任务过程记录在 `tasklist.md`。

区号先尝试键盘输入和鼠标选择；若页面仍保留原区号，使用 `douyin_dom.js` 点击区号输入框所关联列表内的“中国 +86”完整选项。选项被遮挡时停止，选择后和填手机号后都必须确认输入框值为 `+86`。`country_selection` 记录此次选项选择结果。
