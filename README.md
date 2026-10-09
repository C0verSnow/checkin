# 抖音登录截图与搜索页保存

## 新增：抖音登录二维码和短信结果截图

`douyin_login.py` 使用 [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) 打开 `https://www.douyin.com/`，保存登录二维码，然后填入 issue #1 指定的手机号。安装依赖的方法见下方“在 Linux 使用”。

```bash
# 只保存二维码、填入手机号和截图，不发送短信
python douyin_login.py
# 按 issue 要求点击一次“发送验证码”
python douyin_login.py --phone 13657450350 --send-code
# 自定义保存目录；有桌面环境时可以加 --headed 显示浏览器
python douyin_login.py --send-code --output-dir output/douyin-login --timeout-seconds 60
```

输出目录中包含：

| 文件 | 内容 |
| --- | --- |
| `login.png` | 登录页面全图 |
| `login-qr.png` | 登录二维码单独截图 |
| `before-send.png` | 填好手机号后的页面 |
| `sms-result.png` | 点击后的页面，失败时也是实际现场 |
| `result.json` | 时间、手机号、是否点击、结果和页面提示 |

只在页面明确显示验证码已发送时，报告才写 `sent`。仅出现倒计时写 `countdown_only`，不能证明短信已送到手机；安全验证写 `verification_required`，发送失败写 `failed`，其他情况写 `unknown` 或 `error`，均返回非零退出码。脚本不填写收到的验证码、不处理安全验证，也不会自动重试发送短信。二维码未加载时保存现场并停止，不继续发送。每次运行清理该目录内的旧截图，避免把上次结果当成本次结果。

GitHub Actions 的 **Douyin login screenshots** 在 feature 分支 push 和 PR 时用真实 CloakBrowser 检查测试页面，覆盖成功、失败、安全验证、只有倒计时和只截图五种情况。测试页面不会访问抖音或发送短信。实际抖音截图只在手动运行时执行：选择 feature 分支，勾选 `send_code` 才点击一次发送。附件 `douyin-login` 提供实际 PNG、结果报告及 Python 脚本，保留 7 天。截图含手机号与当时的登录二维码，请按实际需要保存附件。网站可访问性和发送结果取决于抖音与 runner 网络，不能把测试页面通过当成真实短信发送成功。

## 用 CloakBrowser 保存可离线打开的搜索页

两个 Python 入口脚本在 Linux 上打开“罗生门”搜索页，保存浏览器运行 JavaScript 后的页面，并把显示需要的 CSS、图片、SVG 和字体放进同一个 UTF-8 HTML 文件。把文件复制到 Windows、macOS 或 Linux 电脑，双击即可离线查看抓取时的页面。点击保存的视频链接会联网打开原网站。

| 脚本 | 页面 | 默认输出 |
| --- | --- | --- |
| `douyin.py` | [抖音搜索](https://www.douyin.com/search/%E7%BD%97%E7%94%9F%E9%97%A8) | `output/douyin.html` |
| `bilibili.py` | [B 站搜索](https://search.bilibili.com/all?keyword=%E7%BD%97%E7%94%9F%E9%97%A8) | `output/bilibili.html` |

## 在 Linux 使用

需要 Python 3.10 或更新版本，推荐 Ubuntu 24.04。请在仓库根目录运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
# 安装 Chromium 所需的 Linux 系统库；这一步可能需要 sudo。
python -m playwright install-deps chromium
python douyin.py
python bilibili.py
```

两个入口共用 `capture_page.py` 和 `offline_page.py`。首次运行会用当前 Python 的 pip 补装缺少的 CloakBrowser、Beautiful Soup、tinycss2 和 html5lib；已经安装就直接使用。CloakBrowser 启动时自动下载并缓存浏览器，需要能访问 PyPI 和浏览器下载站。安装和调用方法见 [CloakBrowser 官方说明](https://github.com/CloakHQ/CloakBrowser)。

默认无界面运行，不需要桌面环境。每次导航最多等 60 秒，页面加载后再等 15 秒，让 JavaScript 更新页面。可以修改保存位置和等待时间：

```bash
python douyin.py --output output/custom-douyin.html --wait-seconds 30 --timeout-seconds 90
python bilibili.py --output output/custom-bilibili.html --wait-seconds 30
```

## 打开保存的页面

输出目录自动创建，同名 HTML 会覆盖。CSS 的嵌套引用、背景图片和字体一起保存；响应式图片保存浏览器当前选中的版本，外部 SVG 图标放进 HTML。下载时优先复用浏览器已加载的响应，缺少的资源用浏览器的 Cookie 和来源地址补抓。资源以内嵌数据形式保存，不需要资源文件夹或本地服务器。

每个 HTML 旁边有一个同名的 `.resources.json` 报告，记录保存了多少资源和哪些资源失败。网站拒绝、网络超时或循环引用会打印提醒，失败的部分可能显示不完整，请查看报告并在网络正常时重试。HTML 停用原站脚本，避免打开后重新联网加载或跳回登录页。

网站的 CSS 还可能引用其他页面或隐藏弹窗的图片。无法下载的图片如果没有用于抓取时任何可见元素或伪元素，会单独记在 `unavailable_unused_images` 中；当前页面需要的资源失败则记在 `failed_resources` 中。远端检查要求当前页面资源无失败、可见图片无损坏且没有外部请求。

保存范围是等待结束时已加载的页面。没有滚动到的内容、之后才出现的弹窗、嵌入的其他网页以及视频流不在保存范围内；跨域图片画到 Canvas 后，浏览器也可能禁止导出。登录、继续搜索、播放视频等操作请在原网站完成。原页面中存在的正常视频链接会保留并转成完整网址。

如果网站返回登录页、验证码或地区限制页，会保存当时的页面，不保证有搜索结果，也不自动登录或处理验证码。HTTP 400 以上的错误页保存供排查，同时脚本返回失败；安装、浏览器启动或导航失败也返回非零退出码。程序结束时关闭浏览器。

## GitHub 上的 Linux 测试和下载

`.github/workflows/capture.yml` 在 push、PR 和手动运行时执行：

1. 测试自动安装、UTF-8 保存、超时清理、HTTP 错误处理、嵌套 CSS、字体、图片、SVG 和资源失败报告。
2. 用真实 CloakBrowser 保存测试网页，再用一个新的、断网的浏览器通过 `file://` 打开文件，检查文字、CSS、伪元素、字体、背景图片、响应式图片、SVG 和视频链接，并确认没有 HTTP 请求。截图在 `offline-verification` 附件中。
3. 分别运行抖音、B 站脚本，再断网打开两个真实网站的 HTML，检查资源失败、可见图片和外部请求，并保存截图。上传 `douyin-html` 和 `bilibili-html` 两个附件，包含 HTML、资源报告、打开检查报告和截图，保留 7 天。

打开 **Actions → Linux HTML capture → 对应运行 → Artifacts** 下载并解压附件，双击 HTML 查看。两个网站分别运行，其中一个失败不会取消另一个；错误页也会上传。外部网站能否访问取决于网站和 GitHub runner 的网络。

按仓库约定，不在本地进行构建、编译或会触发编译的测试。运行验证放在远端 Linux CI；执行过程和运行结果记录在 `tasklist.md`。
