# 抖音登录接口与截图

仓库保留抖音登录相关 Python 和 JavaScript 脚本。`douyin_export.py` 使用 CloakBrowser 登录页面：先直接把可编辑区号框从 `+1` 改成 `+86`，再填手机号，按需点击一次“获取验证码”，记录网站生成的请求和接口返回。浏览器短信不拦截。

本轮按用户选择由浏览器发送一次，`douyin_requests.py` 只重放二维码请求，保存真实接口二维码。网站签名、Cookie 和风控可能使请求失效；脚本不自动重试，也不代过安全验证。

## 安装

需要 Python 3.10+，远端检查使用 Ubuntu 24.04：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install-deps chromium
```

首次启动 CloakBrowser 会下载浏览器。Linux 有窗口模式需要 Xvfb。`browser_setup.py` 不自动安装依赖。

## 只保存二维码，不发送短信

```bash
python douyin_export.py --phone 13657450350
python douyin_requests.py --bundle output/douyin-api/request-bundle.json
```

## 浏览器发送一次并读取接口返回

```bash
python douyin_export.py --phone 13657450350 --send-code
python douyin_requests.py --bundle output/douyin-api/request-bundle.json
```

第一条命令会实际点击一次发送按钮，不拦截短信。旧参数 `--capture-sms` 是 `--send-code` 的别名，也会实际发送。区号输入后、失焦后和填手机号后都会检查；被页面改回时停止。

第二条只验证二维码。不要为这次操作给 requests 加 `--send-code`：请求文件记录 `sms_attempted`，浏览器已经尝试发送或记录缺失时，requests 会拒绝短信重放。接口脚本仍保留短信调用能力，但只接受明确记录未发送的请求文件，并通过独占 `.sms-attempted` 文件限制一次调用；超时或失败后也不重复发送，不删除标记重试。

请求文件包含签名和会话 Cookie，权限为 `0600`，默认保存在 Git 忽略的 `output/`。不要提交或分享。手动远端流程结束后删除请求文件，不上传它。可通过 `--output-dir`、`--timeout-seconds` 设置输出目录和超时，通过 `--headed` 显示窗口。

## 输出

| 文件 | 内容 |
| --- | --- |
| `douyin_login.py` | CloakBrowser 登录、二维码截图和短信返回记录 |
| `douyin_dom.js` | 让真实输入框获得焦点的 JavaScript |
| `douyin_export.py` | 记录请求，不拦截浏览器短信 |
| `douyin_requests.py` | 独立 Python requests 接口入口 |
| `login-qr.png` / `login.png` | 浏览器二维码和登录页面 |
| `before-send.png` / `after-click.png` / `sms-result.png` | 点击前后及结果页面 |
| `result.json` | 浏览器点击、短信接口状态、业务结果和网页反馈 |
| `request-bundle.json` | 私密请求输入及浏览器发送标记 |
| `export-result.json` | 请求捕获、浏览器发送和读取结果 |
| `api-login-qr.png` | requests 接口返回且可解码的二维码图片 |
| `api-result.json` / `api-result.png` | requests 调用报告；PNG 明确标注为接口报告 |

二维码必须来自接口返回的图片并能解码；浏览器截图不会冒充接口产物。短信只有 HTTP 2xx、明确业务码为 `0`，且没有失败或安全验证信息时才记为 `request_accepted`。这表示服务器接受请求，不保证手机收到。

短信请求从点击前监听浏览器上下文，在请求完成后读取响应体。接口失败优先于网页成功提示；发送频繁或 HTTP 429 记为 `failed/rate_limited`，需要验证记为 `verification_required`，不明确记为 `unknown`。网页先提示成功但接口未读完时继续等到原有超时，超时不补发。`sms_requests`、`sms_responses`、`ui_status` 分别记录请求、接口和网页；`sms_response_state` 区分 `completed`、`network_error`、`pending_timeout` 和 `not_observed`。接口报告不保存完整签名 URL、Cookie 或响应令牌。错误和不明确结果返回非零退出码。

## 远端检查

GitHub Actions 的 **Douyin login screenshots** 在 feature 分支 push 和 PR 时运行真实 CloakBrowser 测试，覆盖区号编辑、延迟返回、限流、安全验证、浏览器发送一次、requests 只验证二维码，以及拒绝重发。测试接口不会访问抖音或发送真实短信。

手动流程的 `phone` 填写已获准使用的完整号码，默认只验证二维码；勾选 `send_code` 后浏览器实际点击一次发送，requests 始终只验证二维码。附件 `douyin-login` 包含 PNG、去除敏感请求信息的报告和 Python/JavaScript 脚本，保留 7 天。

按仓库约定，不进行本地构建、编译或会触发编译的测试。过程和远端结果记录在 `tasklist.md`。本轮真实操作仅获准使用 `+86 13657450350` 一次。
