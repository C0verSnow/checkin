# 抖音登录请求转 requests 与接口二维码

issue #3 的交付流程是：用 CloakBrowser 运行登录页面并记录网站生成的接口请求，再由独立 Python requests 脚本调用二维码接口，将真实返回的二维码图片保存为 PNG。默认流程不发送短信。Python 脚本和真实 PNG 可从手动远端流程的 `douyin-login` 附件一起下载。

```text
douyin_export.py（CloakBrowser 记录签名请求）
  → request-bundle.json（私密输入，不上传）
  → douyin_requests.py（Python requests 调用二维码接口）
  → api-login-qr.png + api-result.json + api-result.png
```

仓库保留抖音登录相关 Python 和 JavaScript 脚本。`douyin_export.py` 使用 CloakBrowser 登录页面：先直接把可编辑区号框从 `+1` 改成 `+86`，再填手机号，按需点击一次“获取验证码”，记录网站生成的请求和接口返回。浏览器短信不拦截。

`douyin_export.py` 通过 CloakBrowser 记录网站生成的签名请求，`douyin_requests.py` 用 Python requests 原样调用接口，保存真实接口二维码。仓库还保留明确加 `--send-code` 时发送一次验证码的可选能力；这不是最新 issue #3 的验收要求。网站签名、Cookie 和风控可能使请求失效；脚本不自动重试，也不代过安全验证。

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

这是 issue #3 的默认用法。两条命令连续运行，避免捕获的签名和会话过期：

```bash
python douyin_export.py --phone 13657450350
python douyin_requests.py --bundle output/douyin-api/request-bundle.json
```

转换工具是 `douyin_export.py`：它监听真实浏览器请求，记录方法、完整签名 URL、请求头和原始请求体，供 `douyin_requests.py` 使用。requests 入口运行时不启动浏览器；更换账号或请求失效后需要重新捕获。浏览器二维码截图扫描支持图片、canvas 和 SVG；只有可解码的二维码才保存。

## 记录浏览器请求，再用 requests 发送一次并读取接口返回

```bash
python douyin_export.py --phone 13657450350 --send-code
python douyin_requests.py --bundle output/douyin-api/request-bundle.json --send-code
```

第一条命令会实际点击一次发送按钮，不拦截短信。旧参数 `--capture-sms` 是 `--send-code` 的别名，也会实际发送。区号通过原生输入值设置并通知 input/change 事件，输入后、失焦后和填手机号后都会检查；被页面改回时停止。

第二条保存接口二维码，并额外通过 requests 发送一次短信。记录短信签名请求需要点击按钮，所以这两条命令会先由浏览器尝试发送一次，再由 requests 尝试发送一次；未加 `--send-code` 的 requests 只保存二维码。浏览器请求不拦截，失败也不会伪装成成功。请求文件保留浏览器发送标记；记录缺失时拒绝短信调用。requests 通过独占 `.sms-attempted` 文件限制每个请求文件只发送一次；超时或失败后也不重复发送，不删除标记重试。不要重复运行导出流程来绕过这个限制。

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

GitHub Actions 的 **Douyin login screenshots** 在 feature 分支 push 和 PR 时运行真实 CloakBrowser 测试，覆盖区号编辑、延迟返回、限流、安全验证、浏览器发送一次、requests 只验证二维码，以及明确开启 requests 短信调用后拒绝重复运行。测试接口不会访问抖音或发送真实短信。

手动运行 **Douyin login screenshots**，选择 feature 分支，保持 `send_code=false`，即可验证 issue #3 的二维码流程；`phone` 只用于浏览器表单准备，不点击发送。勾选 `send_code` 后浏览器实际点击一次发送并记录请求，随后 requests 额外发送一次并保存二维码；这是额外的短信模式。流程按 requests 的二维码结果及所选模式判断成功。浏览器失败会保留实际结果，不阻止已捕获的请求由 requests 独立验证。附件 `douyin-login` 包含 PNG、去除敏感请求信息的报告和 Python/JavaScript 脚本，保留 7 天。

按仓库约定，不进行本地构建、编译或会触发编译的测试。过程和远端结果记录在 `tasklist.md`。issue #3 真实验收只保存二维码，不发送短信；可选短信模式使用已获准接收短信的号码，不自动替换手机号或重试发送。

## issue #3 验证结果

- [TDD 修复前](https://github.com/C0verSnow/checkin/actions/runs/37949798873)：SVG 二维码测试失败，其余 12 个测试通过。
- [修复后完整测试](https://github.com/C0verSnow/checkin/actions/runs/37951146446)：13 个测试全部通过。
- [真实二维码验证与 PNG/Python 附件](https://github.com/C0verSnow/checkin/actions/runs/37950918119)：requests 收到 HTTP 200，保存可解码的 `api-login-qr.png`，`qr_saved=true`、`sms_attempted=false`、`status=not_requested`。

这次真实运行中，浏览器已保存二维码并捕获接口请求，随后填写手机号时报“输入框的内容和预期不一致”。requests 独立二维码流程成功；可选手机号和短信流程仍有这个限制，未宣称真实短信模式通过。
