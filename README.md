# 抖音登录工具

## 新增：抖音登录二维码和短信结果截图

`douyin_login.py` 使用 [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) 打开 `https://www.douyin.com/`，确认二维码图片可以解码后保存，直接把可编辑的区号输入框从 `+1` 改成 `+86` 并确认，再填入 issue #1 指定的手机号。安装依赖的方法见下方“安装”。

```bash
# 只保存二维码、填入手机号和截图，不发送短信
python douyin_login.py
# 按 issue 要求点击一次“发送验证码”
python douyin_login.py --phone 13657450350 --send-code
# 自定义保存目录；有桌面环境时可以加 --headed 显示浏览器
python douyin_login.py --send-code --output-dir output/douyin-login --timeout-seconds 60
```

输出目录中包含：

登录流程启用 CloakBrowser 官方的 `humanize=True`，使用逐字输入和拟人鼠标操作，让页面收到完整的输入过程。仍然只点击一次获取验证码，未知结果不会自动重试。

| 文件 | 内容 |
| --- | --- |
| `login.png` | 登录页面全图 |
| `login-qr.png` | 登录二维码单独截图 |
| `before-send.png` | 填好手机号后的页面 |
| `after-click.png` | 点击后立即保存的页面，保留短暂提示 |
| `sms-result.png` | 点击后的页面，失败时也是实际现场 |
| `result.json` | 时间、手机号、是否点击、结果和页面提示 |

只在页面明确显示验证码已发送时，报告才写 `sent`。短信接口明确返回成功时写 `request_accepted`，表示服务器已接受请求，不能证明手机已收到短信；此状态返回零退出码。HTTP 200 本身不算成功。报告只保留接口地址（去掉查询参数）、HTTP 状态、结果码和提示，不保存接口令牌或 Cookie。脚本记录点击调用是否完成，点击与指针事件作为补充排查信息；页面没有提供事件记录时，继续观察接口返回和截图，不把事件缺失当成发送失败。脚本也检查可见嵌入窗口里的安全验证提示。仅出现倒计时写 `countdown_only`，不能证明短信已送到手机；安全验证写 `verification_required`，发送失败写 `failed`，其他情况写 `unknown` 或 `error`，均返回非零退出码。脚本不填写收到的验证码、不处理安全验证，也不会自动重试发送短信。二维码未加载时保存现场并停止，不继续发送。每次运行清理该目录内的旧截图，避免把上次结果当成本次结果。

GitHub Actions 的 **Douyin login screenshots** 在 feature 分支 push 和 PR 时用真实 CloakBrowser 检查测试页面，覆盖成功、失败、安全验证、只有倒计时和只截图多种情况。测试页面不会访问抖音或发送短信。实际抖音截图只在手动运行时执行，使用 Xvfb 提供桌面并以 `--headed` 启动 CloakBrowser：选择 feature 分支，勾选 `send_code` 才点击一次发送。附件 `douyin-login` 提供实际 PNG、结果报告及 Python 脚本，保留 7 天。截图含手机号与当时的登录二维码，请按实际需要保存附件。网站可访问性和发送结果取决于抖音与 runner 网络，不能把测试页面通过当成真实短信发送成功。

### 本次远端检查记录（2026-10-08）

- [直接编辑区号的实际 CloakBrowser 检查](https://github.com/C0verSnow/checkin/actions/runs/37873427362)通过：输入框为 `+86`、手机号为 `13657450350`，二维码成功解码并保存。这次只截图，没有发送短信。附件 `douyin-login` 包含截图、脚本、依赖列表和说明。
- [登录流程测试](https://github.com/C0verSnow/checkin/actions/runs/37873384781)及[原有搜索页检查](https://github.com/C0verSnow/checkin/actions/runs/37873384838)均通过。
- [此前实际点击发送的一轮](https://github.com/C0verSnow/checkin/actions/runs/37873074736)使用了正确的区号和手机号，但页面没有明确成功提示，报告为 `unknown`，该轮按预期返回失败。已经保存实际发送后截图，不能据此宣称短信已送达，也没有自动重试。

## 安装

需要 Python 3.10 或更新版本，远端检查使用 Ubuntu 24.04：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install-deps chromium
python douyin_login.py
```

`browser_setup.py` 只提供浏览器导入和参数检查。请先安装依赖，程序不会自动运行 pip。首次启动 CloakBrowser 会下载浏览器，需要网络。

## 仓库范围

按 issue #3 要求，此仓库只保留抖音登录相关脚本、说明和远端检查。抖音/B 站搜索页保存脚本、离线页面处理、相关依赖和工作流已删除。原有运行记录保留在 `tasklist.md`，输出不纳入 Git。

按仓库约定，不做本地构建、编译或会触发编译的测试；验证放在 GitHub Actions 的 Linux 环境。
