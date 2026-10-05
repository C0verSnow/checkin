# 用 CloakBrowser 保存搜索页

两个 Python 入口脚本在 Linux 上打开“罗生门”搜索页，把浏览器运行 JavaScript 后的 HTML 保存为 UTF-8 文件：

| 脚本 | 页面 | 默认输出 |
| --- | --- | --- |
| `douyin.py` | [抖音搜索](https://www.douyin.com/search/%E7%BD%97%E7%94%9F%E9%97%A8) | `output/douyin.html` |
| `bilibili.py` | [B 站搜索](https://search.bilibili.com/all?keyword=%E7%BD%97%E7%94%9F%E9%97%A8) | `output/bilibili.html` |

## 在 Linux 使用

需要 Python 3.10 或更新版本，推荐 Ubuntu 24.04。请在仓库根目录运行：

```bash
python3 -m venv .venv
source .venv/bin/activate

# 安装 Chromium 所需的 Linux 系统库；这一步可能需要 sudo。
python -m pip install playwright
python -m playwright install-deps chromium

python douyin.py
python bilibili.py
```

两个入口共用 `capture_page.py`。首次运行时，这段代码会用当前 Python 执行 `python -m pip install cloakbrowser`；已经安装就直接使用，不重复安装。CloakBrowser 启动时会自动下载并缓存浏览器，需要能访问 PyPI 和浏览器下载站。安装和调用方法见 [CloakBrowser 官方说明](https://github.com/CloakHQ/CloakBrowser)。

默认无界面运行，不需要桌面环境。每次导航最多等 60 秒，页面加载后再等 15 秒，让 JavaScript 更新页面。可以修改保存位置和等待时间：

```bash
python douyin.py --output output/custom-douyin.html --wait-seconds 30 --timeout-seconds 90
python bilibili.py --output output/custom-bilibili.html --wait-seconds 30
```

输出目录会自动创建，同名 HTML 会覆盖。HTML 是当时浏览器页面的快照；图片、视频、样式等外部资源没有打包进来。

如果网站返回登录页、验证码或地区限制页，HTML 会保存当时的页面，不保证一定有搜索结果，也不自动登录或处理验证码。HTTP 400 以上的错误页会保存供排查，同时脚本返回失败；安装、浏览器启动或导航失败也会返回非零退出码。程序结束时会关闭浏览器。

## GitHub 上的 Linux 测试和 HTML 文件

`.github/workflows/capture.yml` 在 push、PR 和手动运行时执行：

1. 测试自动安装、UTF-8 保存、超时清理和 HTTP 错误处理。
2. 启动真实 CloakBrowser，打开测试网页，确认 JavaScript 渲染结果写入 HTML。
3. 分别运行抖音、B 站脚本，并上传 `douyin-html` 和 `bilibili-html` 两个附件，保留 7 天。

打开仓库的 **Actions → Linux HTML capture → 对应运行 → Artifacts** 下载 HTML。两个网站分别运行，其中一个失败不会取消另一个；错误页也会上传，方便查看失败原因。外部网站能否访问仍取决于网站和 GitHub runner 的网络。

按仓库约定，不在本地进行构建、编译或会触发编译的测试。运行验证放在远端 Linux CI；执行过程记录在 `tasklist.md`。

## 本次运行结果

2026-10-05 的 [远端 Linux CI](https://github.com/huan00000/checkin/actions/runs/37318785381) 全部通过：8 个单元测试、真实浏览器渲染测试以及两个网站抓取。B 站 HTML 包含“罗生门”搜索结果和视频链接；抖音保存了搜索页面，但当时提示登录后才能搜索更多视频。这个结果只代表该次运行，网站之后可能改变访问要求。
